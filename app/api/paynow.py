from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from paynow import Paynow
import asyncio
import logging
import os
from datetime import datetime
from decimal import Decimal

from app.database import get_db
from app.models.order import Order, OrderItem, Payment
from app.models.user import User
from app.api.deps import get_current_active_user

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/paynow", tags=["Paynow Payment"])

# Paynow Configuration for both USD and ZWL
PAYNOW_CONFIG = {
    "USD": {
        "integration_id": os.getenv("PAYNOW_USD_INTEGRATION_ID", "21436"),
        "integration_key": os.getenv("PAYNOW_USD_INTEGRATION_KEY", "9597bbe1-5f34-4910-bb1b-58141ade69ba"),
    },
    "ZWL": {
        "integration_id": os.getenv("PAYNOW_ZWL_INTEGRATION_ID", "21437"),
        "integration_key": os.getenv("PAYNOW_ZWL_INTEGRATION_KEY", "357e671f-5419-495e-ab50-36a5c21e3a00"),
    },
    "return_url": os.getenv("PAYNOW_RETURN_URL", "https://houseandhome.co.zw/payment-return"),
    "result_url": os.getenv("PAYNOW_RESULT_URL", "https://houseandhome.co.zw/api/paynow/webhook"),
    "conversion_rate": float(os.getenv("USD_TO_ZWL_RATE", "35"))  # 1 USD = 35 ZWL
}

# Initialize Paynow instances for both currencies
paynow_usd = Paynow(
    PAYNOW_CONFIG["USD"]["integration_id"],
    PAYNOW_CONFIG["USD"]["integration_key"],
    PAYNOW_CONFIG["return_url"],
    PAYNOW_CONFIG["result_url"]
)

paynow_zwl = Paynow(
    PAYNOW_CONFIG["ZWL"]["integration_id"],
    PAYNOW_CONFIG["ZWL"]["integration_key"],
    PAYNOW_CONFIG["return_url"],
    PAYNOW_CONFIG["result_url"]
)

# Pydantic Models
class PaynowPaymentRequest(BaseModel):
    order_id: int
    payment_method: str  # ecocash or onemoney only
    phone_number: str
    currency: str = "USD"  # USD or ZWL

class PaynowPaymentResponse(BaseModel):
    success: bool
    poll_url: Optional[str] = None
    payment_id: str
    instructions: Optional[str] = None
    status: str = "sent"  # Initial status
    message: str = ""
    error_message: Optional[str] = None

class PaynowStatusResponse(BaseModel):
    success: bool
    status: str  # sent, cancelled, paid
    payment_id: str
    amount: float
    currency: str
    reference: str

class PaymentStatusCheckRequest(BaseModel):
    poll_url: str

# Helper function to convert amount if needed
def convert_amount(amount: Decimal, from_currency: str, to_currency: str) -> Decimal:
    """Convert amount between USD and ZWL"""
    if from_currency == to_currency:
        return amount
    
    if from_currency == "USD" and to_currency == "ZWL":
        return amount * Decimal(str(PAYNOW_CONFIG["conversion_rate"]))
    elif from_currency == "ZWL" and to_currency == "USD":
        return amount / Decimal(str(PAYNOW_CONFIG["conversion_rate"]))
    
    return amount

# Background task to check payment status
async def check_payment_status_background(
    poll_url: str,
    payment_id: int,
    db_session: AsyncSession,
    max_attempts: int = 10,
    initial_delay: int = 30,  # Wait 30 seconds for user to enter PIN
    check_interval: int = 15   # Then check every 15 seconds
):
    """Background task to periodically check payment status"""
    paynow = paynow_usd  # Can use either instance for checking status
    
    # Initial wait for user to enter PIN
    logger.info(f"Waiting {initial_delay} seconds for user to confirm payment with PIN...")
    await asyncio.sleep(initial_delay)
    
    for attempt in range(max_attempts):
        
        try:
            # Check status from Paynow
            status_response = paynow.check_transaction_status(poll_url)
            
            async with db_session as db:
                # Get payment record
                result = await db.execute(
                    select(Payment).where(Payment.id == payment_id)
                )
                payment = result.scalar_one_or_none()
                
                if not payment:
                    logger.error(f"Payment {payment_id} not found")
                    return
                
                # Update payment status based on response
                if status_response.paid:
                    payment.status = "completed"
                    payment.processed_at = datetime.utcnow()
                    
                    # Update order
                    order_result = await db.execute(
                        select(Order).where(Order.id == payment.order_id)
                    )
                    order = order_result.scalar_one()
                    order.payment_status = "paid"
                    order.status = "confirmed"
                    
                    await db.commit()
                    logger.info(f"Payment {payment_id} confirmed as paid")
                    return
                    
                elif status_response.status.lower() == "cancelled":
                    payment.status = "failed"
                    payment.failure_reason = "User cancelled or insufficient funds"
                    
                    # Update order
                    order_result = await db.execute(
                        select(Order).where(Order.id == payment.order_id)
                    )
                    order = order_result.scalar_one()
                    order.payment_status = "failed"
                    
                    await db.commit()
                    logger.info(f"Payment {payment_id} was cancelled")
                    return
                
                # If status is "sent", continue checking (user hasn't entered PIN yet)
                if status_response.status.lower() == "sent":
                    logger.info(f"Payment {payment_id} status: sent - waiting for user PIN confirmation")
                
                # Wait before next check
                if attempt < max_attempts - 1:
                    await asyncio.sleep(check_interval)
                
        except Exception as e:
            logger.error(f"Error checking payment status: {str(e)}")
    
    # After max attempts, mark as timeout
    try:
        async with db_session as db:
            result = await db.execute(
                select(Payment).where(Payment.id == payment_id)
            )
            payment = result.scalar_one_or_none()
            if payment and payment.status == "pending":
                payment.status = "timeout"
                await db.commit()
                logger.warning(f"Payment {payment_id} timed out after {max_attempts} attempts")
    except Exception as e:
        logger.error(f"Error updating timeout status: {str(e)}")

# Add this new endpoint for immediate status check after payment initiation
@router.post("/initiate-and-wait", response_model=PaynowStatusResponse)
async def initiate_and_wait_payment(
    payment_request: PaynowPaymentRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Initiate payment and wait for confirmation (synchronous flow).
    This will wait up to 2 minutes for the user to enter their PIN.
    """
    
    # First initiate the payment
    payment_response = await initiate_payment(
        payment_request=payment_request,
        background_tasks=BackgroundTasks(),  # Dummy, we won't use background task here
        current_user=current_user,
        db=db
    )
    
    if not payment_response.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=payment_response.error_message
        )
    
    # Wait initial period for user to see prompt and enter PIN
    logger.info(f"Waiting 30 seconds for user to enter PIN...")
    await asyncio.sleep(30)
    
    # Now check status periodically
    paynow = paynow_usd
    max_checks = 6  # Check 6 times
    check_interval = 10  # Every 10 seconds (total 90 seconds including initial wait)
    
    for i in range(max_checks):
        try:
            status_response = paynow.check_transaction_status(payment_response.poll_url)
            
            if status_response.paid or status_response.status.lower() == "paid":
                # Payment successful
                logger.info(f"Payment confirmed!")
                
                # Update database
                result = await db.execute(
                    select(Payment).where(Payment.transaction_id == payment_response.payment_id)
                )
                payment = result.scalar_one_or_none()
                if payment:
                    payment.status = "completed"
                    payment.processed_at = datetime.utcnow()
                    
                    order_result = await db.execute(
                        select(Order).where(Order.id == payment.order_id)
                    )
                    order = order_result.scalar_one()
                    order.payment_status = "paid"
                    order.status = "confirmed"
                    await db.commit()
                
                return PaynowStatusResponse(
                    success=True,
                    status="paid",
                    payment_id=payment_response.payment_id,
                    amount=float(payment.amount) if payment else 0,
                    currency=payment.currency if payment else "USD",
                    reference=payment_response.payment_id
                )
                
            elif status_response.status.lower() == "cancelled":
                # Payment cancelled
                logger.info(f"Payment cancelled by user or insufficient funds")
                
                # Update database
                result = await db.execute(
                    select(Payment).where(Payment.transaction_id == payment_response.payment_id)
                )
                payment = result.scalar_one_or_none()
                if payment:
                    payment.status = "failed"
                    payment.failure_reason = "Cancelled or insufficient funds"
                    
                    order_result = await db.execute(
                        select(Order).where(Order.id == payment.order_id)
                    )
                    order = order_result.scalar_one()
                    order.payment_status = "failed"
                    await db.commit()
                
                return PaynowStatusResponse(
                    success=False,
                    status="cancelled",
                    payment_id=payment_response.payment_id,
                    amount=float(payment.amount) if payment else 0,
                    currency=payment.currency if payment else "USD",
                    reference=payment_response.payment_id
                )
            
            # Status is still "sent" - waiting for PIN
            logger.info(f"Check {i+1}/{max_checks}: Payment status is 'sent' - waiting for PIN confirmation...")
            
            if i < max_checks - 1:
                await asyncio.sleep(check_interval)
                
        except Exception as e:
            logger.error(f"Error checking status: {str(e)}")
            
    # Timeout - user didn't complete payment
    return PaynowStatusResponse(
        success=False,
        status="timeout",
        payment_id=payment_response.payment_id,
        amount=0,
        currency="USD",
        reference=payment_response.payment_id
    )

# API Endpoints
@router.post("/initiate", response_model=PaynowPaymentResponse)
async def initiate_payment(
    payment_request: PaynowPaymentRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Initiate Paynow payment for an order (Ecocash or OneMoney only)"""
    
    # Validate payment method
    if payment_request.payment_method not in ["ecocash", "onemoney"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only Ecocash and OneMoney payments are supported"
        )
    
    # Validate currency
    if payment_request.currency not in ["USD", "ZWL"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Currency must be USD or ZWL"
        )
    
    # Get order with items
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.order_items))
        .where(
            and_(
                Order.id == payment_request.order_id,
                Order.user_id == current_user.id
            )
        )
    )
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    if order.payment_status == "paid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order is already paid"
        )
    
    if not order.order_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order has no items"
        )
    
    # Select correct Paynow instance based on currency
    paynow = paynow_zwl if payment_request.currency == "ZWL" else paynow_usd
    
    # Calculate total amount
    total_amount = order.total_amount
    
    # Convert amount if payment is in ZWL
    if payment_request.currency == "ZWL":
        total_amount = convert_amount(total_amount, "USD", "ZWL")
    
    # Create payment reference
    reference = f"Order#{order.order_number}"
    
    try:
        # Create Paynow payment
        payment = paynow.create_payment(reference, current_user.email)
        
        # Add items to payment
        payment_description = f"Payment for order #{order.order_number}"
        payment.add(payment_description, float(total_amount))
        
        # Send mobile payment
        response = paynow.send_mobile(
            payment, 
            payment_request.phone_number, 
            payment_request.payment_method
        )
        
        if not response.success:
            error_message = response.error if hasattr(response, 'error') else "Payment initiation failed"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_message
            )
        
        # Create or update payment record
        payment_result = await db.execute(
            select(Payment).where(Payment.order_id == order.id)
        )
        payment_record = payment_result.scalar_one_or_none()
        
        if not payment_record:
            payment_record = Payment(
                order_id=order.id,
                payment_method=payment_request.payment_method,
                amount=total_amount,
                currency=payment_request.currency,
                status="pending"
            )
            db.add(payment_record)
        else:
            payment_record.payment_method = payment_request.payment_method
            payment_record.amount = total_amount
            payment_record.currency = payment_request.currency
            payment_record.status = "pending"
        
        # Store poll URL and transaction details
        payment_record.transaction_id = reference
        payment_record.gateway_response = {
            "poll_url": response.poll_url,
            "instructions": response.instructions if hasattr(response, 'instructions') else None
        }
        
        # Update order status
        order.payment_status = "pending"
        
        await db.commit()
        await db.refresh(payment_record)
        
        # Schedule background task to check payment status
        background_tasks.add_task(
            check_payment_status_background,
            response.poll_url,
            payment_record.id,
            db
        )
        
        logger.info(f"Payment initiated successfully for order {order.id}")
        
        return PaynowPaymentResponse(
            success=True,
            poll_url=response.poll_url,
            payment_id=reference,
            instructions=response.instructions if hasattr(response, 'instructions') else "Please complete payment on your phone",
            status="sent",
            message="Payment initiated successfully! Please enter your PIN on your phone to confirm the payment. We'll check the status automatically."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Payment initiation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Payment service error: {str(e)}"
        )

@router.post("/check-status", response_model=PaynowStatusResponse)
async def check_payment_status(
    status_request: PaymentStatusCheckRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Manually check payment status using poll URL"""
    
    try:
        # Use either paynow instance (they can both check status)
        paynow = paynow_usd
        status_response = paynow.check_transaction_status(status_request.poll_url)
        
        # Interpret the status
        status_interpretation = {
            "sent": "Payment initiated, waiting for PIN confirmation",
            "cancelled": "Payment cancelled or insufficient funds",
            "paid": "Payment confirmed successfully"
        }
        
        # Find payment by poll URL
        result = await db.execute(
            select(Payment).join(Order).where(
                and_(
                    Payment.gateway_response.contains(status_request.poll_url),
                    Order.user_id == current_user.id
                )
            )
        )
        payment = result.scalar_one_or_none()
        
        if payment:
            # Update payment status based on Paynow response
            if status_response.paid or status_response.status.lower() == "paid":
                payment.status = "completed"
                payment.processed_at = datetime.utcnow()
                
                # Update order
                order_result = await db.execute(
                    select(Order).where(Order.id == payment.order_id)
                )
                order = order_result.scalar_one()
                order.payment_status = "paid"
                order.status = "confirmed"
                logger.info(f"Payment confirmed for order {order.id}")
                
            elif status_response.status.lower() == "cancelled":
                payment.status = "failed"
                payment.failure_reason = "User cancelled or insufficient funds"
                
                # Update order
                order_result = await db.execute(
                    select(Order).where(Order.id == payment.order_id)
                )
                order = order_result.scalar_one()
                order.payment_status = "failed"
                logger.info(f"Payment cancelled for order {order.id}")
            
            elif status_response.status.lower() == "sent":
                # Payment is still pending, user hasn't entered PIN yet
                logger.info(f"Payment still waiting for PIN confirmation for order {payment.order_id}")
            
            await db.commit()
        
        return PaynowStatusResponse(
            success=True,
            status=status_response.status,
            payment_id=payment.transaction_id if payment else "unknown",
            amount=float(payment.amount) if payment else 0,
            currency=payment.currency if payment else "USD",
            reference=payment.transaction_id if payment else "unknown"
        )
        
    except Exception as e:
        logger.error(f"Status check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Status check failed: {str(e)}"
        )

@router.get("/status/{order_id}", response_model=PaynowStatusResponse)
async def get_order_payment_status(
    order_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get payment status for an order"""
    
    # Get payment record
    result = await db.execute(
        select(Payment).join(Order).where(
            and_(
                Payment.order_id == order_id,
                Order.user_id == current_user.id
            )
        )
    )
    payment = result.scalar_one_or_none()
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found for this order"
        )
    
    # Map internal status to Paynow status
    status_mapping = {
        "pending": "sent",
        "completed": "paid",
        "failed": "cancelled",
        "timeout": "timeout"
    }
    
    return PaynowStatusResponse(
        success=True,
        status=status_mapping.get(payment.status, payment.status),
        payment_id=payment.transaction_id,
        amount=float(payment.amount),
        currency=payment.currency,
        reference=payment.transaction_id
    )

# Add this endpoint to your existing paynow.py router

@router.post("/complete-payment", response_model=Dict[str, Any])
async def complete_payment_sync(
    payment_request: PaynowPaymentRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Complete payment synchronously - waits for payment confirmation.
    This endpoint will:
    1. Initiate the payment
    2. Wait for user to enter PIN (30 seconds)
    3. Check status periodically
    4. Return final status
    """
    
    # Validate payment method
    if payment_request.payment_method not in ["ecocash", "onemoney"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only Ecocash and OneMoney payments are supported"
        )
    
    # Validate currency
    if payment_request.currency not in ["USD", "ZWL"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Currency must be USD or ZWL"
        )
    
    # Get order with items
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.order_items))
        .where(
            and_(
                Order.id == payment_request.order_id,
                Order.user_id == current_user.id
            )
        )
    )
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    if order.payment_status == "paid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order is already paid"
        )
    
    # Select correct Paynow instance based on currency
    paynow = paynow_zwl if payment_request.currency == "ZWL" else paynow_usd
    
    # Calculate total amount
    total_amount = order.total_amount
    
    # Convert amount if payment is in ZWL
    if payment_request.currency == "ZWL":
        total_amount = convert_amount(total_amount, "USD", "ZWL")
    
    # Create payment reference
    reference = f"Order#{order.order_number}"
    
    try:
        # Step 1: Create Paynow payment
        payment = paynow.create_payment(reference, current_user.email)
        payment_description = f"Payment for order #{order.order_number}"
        payment.add(payment_description, float(total_amount))
        
        # Step 2: Send mobile payment
        logger.info(f"Initiating payment for {payment_request.phone_number} via {payment_request.payment_method}")
        response = paynow.send_mobile(
            payment, 
            payment_request.phone_number, 
            payment_request.payment_method
        )
        
        if not response.success:
            error_message = response.error if hasattr(response, 'error') else "Payment initiation failed"
            logger.error(f"Payment initiation failed: {error_message}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_message
            )
        
        # Step 3: Create payment record
        payment_result = await db.execute(
            select(Payment).where(Payment.order_id == order.id)
        )
        payment_record = payment_result.scalar_one_or_none()
        
        if not payment_record:
            payment_record = Payment(
                order_id=order.id,
                payment_method=payment_request.payment_method,
                amount=total_amount,
                currency=payment_request.currency,
                status="pending"
            )
            db.add(payment_record)
        else:
            payment_record.payment_method = payment_request.payment_method
            payment_record.amount = total_amount
            payment_record.currency = payment_request.currency
            payment_record.status = "pending"
        
        payment_record.transaction_id = reference
        payment_record.gateway_response = {
            "poll_url": response.poll_url,
            "instructions": response.instructions if hasattr(response, 'instructions') else None
        }
        
        order.payment_status = "pending"
        await db.commit()
        await db.refresh(payment_record)
        
        logger.info(f"Payment initiated successfully. Poll URL: {response.poll_url}")
        logger.info("Waiting 30 seconds for user to enter PIN...")
        
        # Step 4: Wait for user to enter PIN (30 seconds)
        await asyncio.sleep(30)
        
        # Step 5: Check payment status periodically
        max_checks = 6  # Check 6 times
        check_interval = 10  # Every 10 seconds
        final_status = "timeout"
        
        for i in range(max_checks):
            try:
                logger.info(f"Checking payment status (attempt {i+1}/{max_checks})...")
                status_response = paynow.check_transaction_status(response.poll_url)
                
                # Check if payment is paid
                if hasattr(status_response, 'paid') and status_response.paid:
                    logger.info("✅ Payment CONFIRMED!")
                    final_status = "paid"
                    
                    # Update payment and order
                    payment_record.status = "completed"
                    payment_record.processed_at = datetime.utcnow()
                    order.payment_status = "paid"
                    order.status = "confirmed"
                    await db.commit()
                    
                    return {
                        "success": True,
                        "status": "paid",
                        "payment_id": reference,
                        "order_id": order.id,
                        "message": "Payment completed successfully!",
                        "amount": float(total_amount),
                        "currency": payment_request.currency
                    }
                
                elif status_response.status.lower() == "cancelled":
                    logger.info("❌ Payment CANCELLED by user or insufficient funds")
                    final_status = "cancelled"
                    
                    # Update payment and order
                    payment_record.status = "failed"
                    payment_record.failure_reason = "Cancelled or insufficient funds"
                    order.payment_status = "failed"
                    await db.commit()
                    
                    return {
                        "success": False,
                        "status": "cancelled",
                        "payment_id": reference,
                        "order_id": order.id,
                        "message": "Payment was cancelled or failed due to insufficient funds",
                        "amount": float(total_amount),
                        "currency": payment_request.currency
                    }
                
                elif status_response.status.lower() == "sent":
                    logger.info(f"⏳ Payment still pending (status: sent) - waiting for PIN confirmation...")
                
                # Wait before next check (except for last iteration)
                if i < max_checks - 1:
                    await asyncio.sleep(check_interval)
                    
            except Exception as e:
                logger.error(f"Error checking status: {str(e)}")
                if i < max_checks - 1:
                    await asyncio.sleep(check_interval)
        
        # Step 6: Handle timeout
        logger.warning(f"⏱️ Payment timed out after {30 + (max_checks * check_interval)} seconds")
        payment_record.status = "timeout"
        order.payment_status = "timeout"
        await db.commit()
        
        return {
            "success": False,
            "status": "timeout",
            "payment_id": reference,
            "order_id": order.id,
            "message": "Payment request timed out. User did not complete the payment in time.",
            "amount": float(total_amount),
            "currency": payment_request.currency
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Payment processing failed: {str(e)}")
        
        # Update payment status on error
        if 'payment_record' in locals():
            payment_record.status = "failed"
            payment_record.failure_reason = str(e)
            await db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Payment service error: {str(e)}"
        )

# Alternative: Async version with immediate response + status polling
@router.post("/initiate-with-polling", response_model=Dict[str, Any])
async def initiate_payment_with_polling(
    payment_request: PaynowPaymentRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Initiate payment and return immediately with poll URL.
    Frontend can then poll the status endpoint.
    """
    
    # [Previous validation code same as initiate endpoint...]
    
    # Initiate payment (similar to existing initiate endpoint)
    # ... 
    
    # But return more detailed response for frontend polling
    return {
        "success": True,
        "poll_url": response.poll_url,
        "payment_id": reference,
        "order_id": order.id,
        "instructions": response.instructions if hasattr(response, 'instructions') else "Please enter your PIN on your phone",
        "status": "sent",
        "message": "Payment initiated. Please check your phone and enter PIN.",
        "expected_wait_time": 30,  # Tell frontend to wait 30 seconds before first check
        "polling_interval": 10,     # Tell frontend to check every 10 seconds
        "max_polls": 6             # Tell frontend max number of checks
    }

@router.get("/test-config")
async def test_config():
    """Test endpoint to verify Paynow configuration"""
    return {
        "USD": {
            "integration_id": PAYNOW_CONFIG["USD"]["integration_id"],
            "configured": bool(PAYNOW_CONFIG["USD"]["integration_key"])
        },
        "ZWL": {
            "integration_id": PAYNOW_CONFIG["ZWL"]["integration_id"],
            "configured": bool(PAYNOW_CONFIG["ZWL"]["integration_key"])
        },
        "conversion_rate": PAYNOW_CONFIG["conversion_rate"],
        "return_url": PAYNOW_CONFIG["return_url"],
        "result_url": PAYNOW_CONFIG["result_url"],
        "supported_methods": ["ecocash", "onemoney"]
    }

__all__ = ["router"]


# from typing import Optional, Dict, Any
# from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select, and_
# from sqlalchemy.orm import selectinload
# from pydantic import BaseModel
# from paynow import Paynow
# import asyncio
# import logging
# import os
# from datetime import datetime
# from decimal import Decimal

# from app.database import get_db
# from app.models.order import Order, OrderItem, Payment
# from app.models.user import User
# from app.api.deps import get_current_active_user

# # Configure logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# router = APIRouter(prefix="/paynow", tags=["Paynow Payment"])

# # Paynow Configuration for both USD and ZWL
# PAYNOW_CONFIG = {
#     "USD": {
#         "integration_id": os.getenv("PAYNOW_USD_INTEGRATION_ID", "21436"),
#         "integration_key": os.getenv("PAYNOW_USD_INTEGRATION_KEY", "9597bbe1-5f34-4910-bb1b-58141ade69ba"),
#     },
#     "ZWL": {
#         "integration_id": os.getenv("PAYNOW_ZWL_INTEGRATION_ID", "21437"),
#         "integration_key": os.getenv("PAYNOW_ZWL_INTEGRATION_KEY", "357e671f-5419-495e-ab50-36a5c21e3a00"),
#     },
#     "return_url": os.getenv("PAYNOW_RETURN_URL", "https://houseandhome.co.zw/payment-return"),
#     "result_url": os.getenv("PAYNOW_RESULT_URL", "https://houseandhome.co.zw/api/paynow/webhook"),
#     "conversion_rate": float(os.getenv("USD_TO_ZWL_RATE", "35"))  # 1 USD = 35 ZWL
# }

# # Initialize Paynow instances for both currencies
# paynow_usd = Paynow(
#     PAYNOW_CONFIG["USD"]["integration_id"],
#     PAYNOW_CONFIG["USD"]["integration_key"],
#     PAYNOW_CONFIG["return_url"],
#     PAYNOW_CONFIG["result_url"]
# )

# paynow_zwl = Paynow(
#     PAYNOW_CONFIG["ZWL"]["integration_id"],
#     PAYNOW_CONFIG["ZWL"]["integration_key"],
#     PAYNOW_CONFIG["return_url"],
#     PAYNOW_CONFIG["result_url"]
# )

# # Pydantic Models
# class PaynowPaymentRequest(BaseModel):
#     order_id: int
#     payment_method: str  # ecocash or onemoney only
#     phone_number: str
#     currency: str = "USD"  # USD or ZWL

# class PaynowPaymentResponse(BaseModel):
#     success: bool
#     poll_url: Optional[str] = None
#     payment_id: str
#     instructions: Optional[str] = None
#     status: str = "sent"  # Initial status
#     message: str = ""
#     error_message: Optional[str] = None

# class PaynowStatusResponse(BaseModel):
#     success: bool
#     status: str  # sent, cancelled, paid
#     payment_id: str
#     amount: float
#     currency: str
#     reference: str

# class PaymentStatusCheckRequest(BaseModel):
#     poll_url: str

# # Helper function to convert amount if needed
# def convert_amount(amount: Decimal, from_currency: str, to_currency: str) -> Decimal:
#     """Convert amount between USD and ZWL"""
#     if from_currency == to_currency:
#         return amount
    
#     if from_currency == "USD" and to_currency == "ZWL":
#         return amount * Decimal(str(PAYNOW_CONFIG["conversion_rate"]))
#     elif from_currency == "ZWL" and to_currency == "USD":
#         return amount / Decimal(str(PAYNOW_CONFIG["conversion_rate"]))
    
#     return amount

# # Background task to check payment status
# async def check_payment_status_background(
#     poll_url: str,
#     payment_id: int,
#     db_session: AsyncSession,
#     max_attempts: int = 10,
#     initial_delay: int = 30,  # Wait 30 seconds for user to enter PIN
#     check_interval: int = 15   # Then check every 15 seconds
# ):
#     """Background task to periodically check payment status"""
#     paynow = paynow_usd  # Can use either instance for checking status
    
#     # Initial wait for user to enter PIN
#     logger.info(f"Waiting {initial_delay} seconds for user to confirm payment with PIN...")
#     await asyncio.sleep(initial_delay)
    
#     for attempt in range(max_attempts):
        
#         try:
#             # Check status from Paynow
#             status_response = paynow.check_transaction_status(poll_url)
            
#             async with db_session as db:
#                 # Get payment record
#                 result = await db.execute(
#                     select(Payment).where(Payment.id == payment_id)
#                 )
#                 payment = result.scalar_one_or_none()
                
#                 if not payment:
#                     logger.error(f"Payment {payment_id} not found")
#                     return
                
#                 # Update payment status based on response
#                 if status_response.paid:
#                     payment.status = "completed"
#                     payment.processed_at = datetime.utcnow()
                    
#                     # Update order
#                     order_result = await db.execute(
#                         select(Order).where(Order.id == payment.order_id)
#                     )
#                     order = order_result.scalar_one()
#                     order.payment_status = "paid"
#                     order.status = "confirmed"
                    
#                     await db.commit()
#                     logger.info(f"Payment {payment_id} confirmed as paid")
#                     return
                    
#                 elif status_response.status.lower() == "cancelled":
#                     payment.status = "failed"
#                     payment.failure_reason = "User cancelled or insufficient funds"
                    
#                     # Update order
#                     order_result = await db.execute(
#                         select(Order).where(Order.id == payment.order_id)
#                     )
#                     order = order_result.scalar_one()
#                     order.payment_status = "failed"
                    
#                     await db.commit()
#                     logger.info(f"Payment {payment_id} was cancelled")
#                     return
                
#                 # If status is "sent", continue checking (user hasn't entered PIN yet)
#                 if status_response.status.lower() == "sent":
#                     logger.info(f"Payment {payment_id} status: sent - waiting for user PIN confirmation")
                
#                 # Wait before next check
#                 if attempt < max_attempts - 1:
#                     await asyncio.sleep(check_interval)
                
#         except Exception as e:
#             logger.error(f"Error checking payment status: {str(e)}")
    
#     # After max attempts, mark as timeout
#     try:
#         async with db_session as db:
#             result = await db.execute(
#                 select(Payment).where(Payment.id == payment_id)
#             )
#             payment = result.scalar_one_or_none()
#             if payment and payment.status == "pending":
#                 payment.status = "timeout"
#                 await db.commit()
#                 logger.warning(f"Payment {payment_id} timed out after {max_attempts} attempts")
#     except Exception as e:
#         logger.error(f"Error updating timeout status: {str(e)}")

# # Add this new endpoint for immediate status check after payment initiation
# @router.post("/initiate-and-wait", response_model=PaynowStatusResponse)
# async def initiate_and_wait_payment(
#     payment_request: PaynowPaymentRequest,
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """
#     Initiate payment and wait for confirmation (synchronous flow).
#     This will wait up to 2 minutes for the user to enter their PIN.
#     """
    
#     # First initiate the payment
#     payment_response = await initiate_payment(
#         payment_request=payment_request,
#         background_tasks=BackgroundTasks(),  # Dummy, we won't use background task here
#         current_user=current_user,
#         db=db
#     )
    
#     if not payment_response.success:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail=payment_response.error_message
#         )
    
#     # Wait initial period for user to see prompt and enter PIN
#     logger.info(f"Waiting 30 seconds for user to enter PIN...")
#     await asyncio.sleep(30)
    
#     # Now check status periodically
#     paynow = paynow_usd
#     max_checks = 6  # Check 6 times
#     check_interval = 10  # Every 10 seconds (total 90 seconds including initial wait)
    
#     for i in range(max_checks):
#         try:
#             status_response = paynow.check_transaction_status(payment_response.poll_url)
            
#             if status_response.paid or status_response.status.lower() == "paid":
#                 # Payment successful
#                 logger.info(f"Payment confirmed!")
                
#                 # Update database
#                 result = await db.execute(
#                     select(Payment).where(Payment.transaction_id == payment_response.payment_id)
#                 )
#                 payment = result.scalar_one_or_none()
#                 if payment:
#                     payment.status = "completed"
#                     payment.processed_at = datetime.utcnow()
                    
#                     order_result = await db.execute(
#                         select(Order).where(Order.id == payment.order_id)
#                     )
#                     order = order_result.scalar_one()
#                     order.payment_status = "paid"
#                     order.status = "confirmed"
#                     await db.commit()
                
#                 return PaynowStatusResponse(
#                     success=True,
#                     status="paid",
#                     payment_id=payment_response.payment_id,
#                     amount=float(payment.amount) if payment else 0,
#                     currency=payment.currency if payment else "USD",
#                     reference=payment_response.payment_id
#                 )
                
#             elif status_response.status.lower() == "cancelled":
#                 # Payment cancelled
#                 logger.info(f"Payment cancelled by user or insufficient funds")
                
#                 # Update database
#                 result = await db.execute(
#                     select(Payment).where(Payment.transaction_id == payment_response.payment_id)
#                 )
#                 payment = result.scalar_one_or_none()
#                 if payment:
#                     payment.status = "failed"
#                     payment.failure_reason = "Cancelled or insufficient funds"
                    
#                     order_result = await db.execute(
#                         select(Order).where(Order.id == payment.order_id)
#                     )
#                     order = order_result.scalar_one()
#                     order.payment_status = "failed"
#                     await db.commit()
                
#                 return PaynowStatusResponse(
#                     success=False,
#                     status="cancelled",
#                     payment_id=payment_response.payment_id,
#                     amount=float(payment.amount) if payment else 0,
#                     currency=payment.currency if payment else "USD",
#                     reference=payment_response.payment_id
#                 )
            
#             # Status is still "sent" - waiting for PIN
#             logger.info(f"Check {i+1}/{max_checks}: Payment status is 'sent' - waiting for PIN confirmation...")
            
#             if i < max_checks - 1:
#                 await asyncio.sleep(check_interval)
                
#         except Exception as e:
#             logger.error(f"Error checking status: {str(e)}")
            
#     # Timeout - user didn't complete payment
#     return PaynowStatusResponse(
#         success=False,
#         status="timeout",
#         payment_id=payment_response.payment_id,
#         amount=0,
#         currency="USD",
#         reference=payment_response.payment_id
#     )

# # API Endpoints
# @router.post("/initiate", response_model=PaynowPaymentResponse)
# async def initiate_payment(
#     payment_request: PaynowPaymentRequest,
#     background_tasks: BackgroundTasks,
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Initiate Paynow payment for an order (Ecocash or OneMoney only)"""
    
#     # Validate payment method
#     if payment_request.payment_method not in ["ecocash", "onemoney"]:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Only Ecocash and OneMoney payments are supported"
#         )
    
#     # Validate currency
#     if payment_request.currency not in ["USD", "ZWL"]:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Currency must be USD or ZWL"
#         )
    
#     # Get order with items
#     result = await db.execute(
#         select(Order)
#         .options(selectinload(Order.order_items))
#         .where(
#             and_(
#                 Order.id == payment_request.order_id,
#                 Order.user_id == current_user.id
#             )
#         )
#     )
#     order = result.scalar_one_or_none()
    
#     if not order:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Order not found"
#         )
    
#     if order.payment_status == "paid":
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Order is already paid"
#         )
    
#     if not order.order_items:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Order has no items"
#         )
    
#     # Select correct Paynow instance based on currency
#     paynow = paynow_zwl if payment_request.currency == "ZWL" else paynow_usd
    
#     # Calculate total amount
#     total_amount = order.total_amount
    
#     # Convert amount if payment is in ZWL
#     if payment_request.currency == "ZWL":
#         total_amount = convert_amount(total_amount, "USD", "ZWL")
    
#     # Create payment reference
#     reference = f"Order#{order.order_number}"
    
#     try:
#         # Create Paynow payment
#         payment = paynow.create_payment(reference, current_user.email)
        
#         # Add items to payment
#         payment_description = f"Payment for order #{order.order_number}"
#         payment.add(payment_description, float(total_amount))
        
#         # Send mobile payment
#         response = paynow.send_mobile(
#             payment, 
#             payment_request.phone_number, 
#             payment_request.payment_method
#         )
        
#         if not response.success:
#             error_message = response.error if hasattr(response, 'error') else "Payment initiation failed"
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail=error_message
#             )
        
#         # Create or update payment record
#         payment_result = await db.execute(
#             select(Payment).where(Payment.order_id == order.id)
#         )
#         payment_record = payment_result.scalar_one_or_none()
        
#         if not payment_record:
#             payment_record = Payment(
#                 order_id=order.id,
#                 payment_method=payment_request.payment_method,
#                 amount=total_amount,
#                 currency=payment_request.currency,
#                 status="pending"
#             )
#             db.add(payment_record)
#         else:
#             payment_record.payment_method = payment_request.payment_method
#             payment_record.amount = total_amount
#             payment_record.currency = payment_request.currency
#             payment_record.status = "pending"
        
#         # Store poll URL and transaction details
#         payment_record.transaction_id = reference
#         payment_record.gateway_response = {
#             "poll_url": response.poll_url,
#             "instructions": response.instructions if hasattr(response, 'instructions') else None
#         }
        
#         # Update order status
#         order.payment_status = "pending"
        
#         await db.commit()
#         await db.refresh(payment_record)
        
#         # Schedule background task to check payment status
#         background_tasks.add_task(
#             check_payment_status_background,
#             response.poll_url,
#             payment_record.id,
#             db
#         )
        
#         logger.info(f"Payment initiated successfully for order {order.id}")
        
#         return PaynowPaymentResponse(
#             success=True,
#             poll_url=response.poll_url,
#             payment_id=reference,
#             instructions=response.instructions if hasattr(response, 'instructions') else "Please complete payment on your phone",
#             status="sent",
#             message="Payment initiated successfully! Please enter your PIN on your phone to confirm the payment. We'll check the status automatically."
#         )
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Payment initiation failed: {str(e)}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Payment service error: {str(e)}"
#         )

# @router.post("/check-status", response_model=PaynowStatusResponse)
# async def check_payment_status(
#     status_request: PaymentStatusCheckRequest,
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Manually check payment status using poll URL"""
    
#     try:
#         # Use either paynow instance (they can both check status)
#         paynow = paynow_usd
#         status_response = paynow.check_transaction_status(status_request.poll_url)
        
#         # Interpret the status
#         status_interpretation = {
#             "sent": "Payment initiated, waiting for PIN confirmation",
#             "cancelled": "Payment cancelled or insufficient funds",
#             "paid": "Payment confirmed successfully"
#         }
        
#         # Find payment by poll URL
#         result = await db.execute(
#             select(Payment).join(Order).where(
#                 and_(
#                     Payment.gateway_response.contains(status_request.poll_url),
#                     Order.user_id == current_user.id
#                 )
#             )
#         )
#         payment = result.scalar_one_or_none()
        
#         if payment:
#             # Update payment status based on Paynow response
#             if status_response.paid or status_response.status.lower() == "paid":
#                 payment.status = "completed"
#                 payment.processed_at = datetime.utcnow()
                
#                 # Update order
#                 order_result = await db.execute(
#                     select(Order).where(Order.id == payment.order_id)
#                 )
#                 order = order_result.scalar_one()
#                 order.payment_status = "paid"
#                 order.status = "confirmed"
#                 logger.info(f"Payment confirmed for order {order.id}")
                
#             elif status_response.status.lower() == "cancelled":
#                 payment.status = "failed"
#                 payment.failure_reason = "User cancelled or insufficient funds"
                
#                 # Update order
#                 order_result = await db.execute(
#                     select(Order).where(Order.id == payment.order_id)
#                 )
#                 order = order_result.scalar_one()
#                 order.payment_status = "failed"
#                 logger.info(f"Payment cancelled for order {order.id}")
            
#             elif status_response.status.lower() == "sent":
#                 # Payment is still pending, user hasn't entered PIN yet
#                 logger.info(f"Payment still waiting for PIN confirmation for order {payment.order_id}")
            
#             await db.commit()
        
#         return PaynowStatusResponse(
#             success=True,
#             status=status_response.status,
#             payment_id=payment.transaction_id if payment else "unknown",
#             amount=float(payment.amount) if payment else 0,
#             currency=payment.currency if payment else "USD",
#             reference=payment.transaction_id if payment else "unknown"
#         )
        
#     except Exception as e:
#         logger.error(f"Status check failed: {str(e)}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Status check failed: {str(e)}"
#         )

# @router.get("/status/{order_id}", response_model=PaynowStatusResponse)
# async def get_order_payment_status(
#     order_id: int,
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get payment status for an order"""
    
#     # Get payment record
#     result = await db.execute(
#         select(Payment).join(Order).where(
#             and_(
#                 Payment.order_id == order_id,
#                 Order.user_id == current_user.id
#             )
#         )
#     )
#     payment = result.scalar_one_or_none()
    
#     if not payment:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Payment not found for this order"
#         )
    
#     # Map internal status to Paynow status
#     status_mapping = {
#         "pending": "sent",
#         "completed": "paid",
#         "failed": "cancelled",
#         "timeout": "timeout"
#     }
    
#     return PaynowStatusResponse(
#         success=True,
#         status=status_mapping.get(payment.status, payment.status),
#         payment_id=payment.transaction_id,
#         amount=float(payment.amount),
#         currency=payment.currency,
#         reference=payment.transaction_id
#     )

# @router.get("/test-config")
# async def test_config():
#     """Test endpoint to verify Paynow configuration"""
#     return {
#         "USD": {
#             "integration_id": PAYNOW_CONFIG["USD"]["integration_id"],
#             "configured": bool(PAYNOW_CONFIG["USD"]["integration_key"])
#         },
#         "ZWL": {
#             "integration_id": PAYNOW_CONFIG["ZWL"]["integration_id"],
#             "configured": bool(PAYNOW_CONFIG["ZWL"]["integration_key"])
#         },
#         "conversion_rate": PAYNOW_CONFIG["conversion_rate"],
#         "return_url": PAYNOW_CONFIG["return_url"],
#         "result_url": PAYNOW_CONFIG["result_url"],
#         "supported_methods": ["ecocash", "onemoney"]
#     }

# __all__ = ["router"]

# # from typing import Optional, Dict, Any, List
# # from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
# # from sqlalchemy.ext.asyncio import AsyncSession
# # from sqlalchemy import select, and_
# # from sqlalchemy.orm import selectinload
# # from pydantic import BaseModel
# # from paynow import Paynow
# # import asyncio
# # import logging
# # import os
# # from datetime import datetime
# # from decimal import Decimal

# # from app.database import get_db
# # from app.models.order import Order, OrderItem, Payment
# # from app.models.user import User
# # from app.api.deps import get_current_active_user

# # # Configure logging
# # logging.basicConfig(level=logging.INFO)
# # logger = logging.getLogger(__name__)

# # router = APIRouter(prefix="/paynow", tags=["Paynow Payment"])

# # # Paynow Configuration for USD and ZWL
# # PAYNOW_CONFIGS = {
# #     "USD": {
# #         "integration_id": os.getenv("PAYNOW_USD_INTEGRATION_ID", "21436"),
# #         "integration_key": os.getenv("PAYNOW_USD_INTEGRATION_KEY", "9597bbe1-5f34-4910-bb1b-58141ade69ba"),
# #         "return_url": os.getenv("PAYNOW_RETURN_URL", "https://houseandhome.co.zw/"),
# #         "result_url": os.getenv("PAYNOW_RESULT_URL", "https://houseandhome.co.zw/")
# #     },
# #     "ZWL": {
# #         "integration_id": os.getenv("PAYNOW_ZWL_INTEGRATION_ID", "21437"),
# #         "integration_key": os.getenv("PAYNOW_ZWL_INTEGRATION_KEY", "357e671f-5419-495e-ab50-36a5c21e3a00"),
# #         "return_url": os.getenv("PAYNOW_RETURN_URL", "https://houseandhome.co.zw/"),
# #         "result_url": os.getenv("PAYNOW_RESULT_URL", "https://houseandhome.co.zw/")
# #     }
# # }

# # # Conversion rate
# # USD_TO_ZWL_RATE = 35

# # # Pydantic Models
# # class PaynowMobilePaymentRequest(BaseModel):
# #     order_id: int
# #     payment_method: str  # ecocash or onemoney only
# #     phone_number: str
# #     currency: str = "USD"  # USD or ZWL

# # class PaynowPaymentResponse(BaseModel):
# #     success: bool
# #     poll_url: Optional[str] = None
# #     payment_id: str
# #     status: str
# #     message: str

# # class PaynowStatusResponse(BaseModel):
# #     success: bool
# #     status: str  # sent, paid, cancelled, expired
# #     payment_id: str
# #     amount: float
# #     currency: str
# #     reference: str
# #     message: Optional[str] = None

# # # Helper Functions
# # def get_paynow_client(currency: str = "USD") -> Paynow:
# #     """Get Paynow client for specified currency"""
# #     config = PAYNOW_CONFIGS.get(currency.upper(), PAYNOW_CONFIGS["USD"])
# #     return Paynow(
# #         config["integration_id"],
# #         config["integration_key"],
# #         config["return_url"],
# #         config["result_url"]
# #     )

# # def convert_to_zwl(usd_amount: Decimal) -> Decimal:
# #     """Convert USD to ZWL"""
# #     return usd_amount * Decimal(str(USD_TO_ZWL_RATE))

# # async def check_payment_status_background(
# #     poll_url: str,
# #     payment_id: int,
# #     db: AsyncSession,
# #     currency: str = "USD",
# #     max_attempts: int = 20,
# #     initial_delay: int = 30,
# #     check_interval: int = 15
# # ):
# #     """Background task to check payment status
    
# #     Flow:
# #     1. Wait initial_delay seconds for user to see and confirm PIN prompt
# #     2. Check status every check_interval seconds
# #     3. Stop after max_attempts or when payment completes/fails
# #     """
# #     paynow = get_paynow_client(currency)
    
# #     # Initial delay to give user time to enter PIN
# #     logger.info(f"Payment {payment_id} initiated. Waiting {initial_delay}s for user to enter PIN...")
# #     await asyncio.sleep(initial_delay)
    
# #     for attempt in range(max_attempts):
# #         try:
# #             # Check status
# #             status_response = paynow.check_transaction_status(poll_url)
# #             status = status_response.status.lower()
            
# #             logger.info(f"Payment {payment_id} status check {attempt + 1}/{max_attempts}: {status}")
            
# #             # Get payment record
# #             result = await db.execute(
# #                 select(Payment).where(Payment.id == payment_id)
# #             )
# #             payment = result.scalar_one_or_none()
            
# #             if not payment:
# #                 logger.error(f"Payment {payment_id} not found")
# #                 break
            
# #             # Check if payment is paid
# #             if hasattr(status_response, 'paid') and status_response.paid:
# #                 payment.status = "completed"
# #                 payment.processed_at = datetime.utcnow()
                
# #                 # Update order
# #                 order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
# #                 order = order_result.scalar_one()
# #                 order.payment_status = "paid"
# #                 order.status = "confirmed"
                
# #                 await db.commit()
# #                 logger.info(f"✅ Payment {payment_id} CONFIRMED! Payment completed successfully.")
# #                 break
                
# #             elif status == "cancelled":
# #                 payment.status = "failed"
# #                 payment.gateway_response = f"{payment.gateway_response}|cancelled"
                
# #                 # Update order
# #                 order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
# #                 order = order_result.scalar_one()
# #                 order.payment_status = "failed"
                
# #                 await db.commit()
# #                 logger.info(f"❌ Payment {payment_id} CANCELLED by user or insufficient funds.")
# #                 break
                
# #             elif status == "sent":
# #                 # Payment still pending - user hasn't acted yet
# #                 logger.info(f"⏳ Payment {payment_id} waiting for user action (PIN confirmation)...")
# #                 payment.status = "pending"
# #                 await db.commit()
                
# #             # Wait before next check
# #             if attempt < max_attempts - 1:
# #                 await asyncio.sleep(check_interval)
                
# #         except Exception as e:
# #             logger.error(f"Error checking payment {payment_id} status: {str(e)}")
# #             await asyncio.sleep(check_interval)
            
# #     # Final check if we exhausted attempts
# #     if attempt == max_attempts - 1:
# #         logger.warning(f"⏱️ Payment {payment_id} timed out after {max_attempts * check_interval}s. User did not complete payment.")
        
# #         # Mark as expired
# #         result = await db.execute(select(Payment).where(Payment.id == payment_id))
# #         payment = result.scalar_one_or_none()
# #         if payment and payment.status == "pending":
# #             payment.status = "expired"
# #             order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
# #             order = order_result.scalar_one()
# #             order.payment_status = "expired"
# #             await db.commit()

# # # API Endpoints
# # @router.post("/mobile/initiate", response_model=PaynowPaymentResponse)
# # async def initiate_mobile_payment(
# #     payment_request: PaynowMobilePaymentRequest,
# #     background_tasks: BackgroundTasks,
# #     current_user: User = Depends(get_current_active_user),
# #     db: AsyncSession = Depends(get_db)
# # ):
# #     """Initiate mobile money payment (EcoCash or OneMoney only)"""
    
# #     # Validate payment method
# #     if payment_request.payment_method.lower() not in ["ecocash", "onemoney"]:
# #         raise HTTPException(
# #             status_code=status.HTTP_400_BAD_REQUEST,
# #             detail="Only EcoCash and OneMoney are supported"
# #         )
    
# #     # Validate phone number (Zimbabwe format)
# #     if not payment_request.phone_number.startswith(("07", "08", "+263", "263")):
# #         raise HTTPException(
# #             status_code=status.HTTP_400_BAD_REQUEST,
# #             detail="Invalid phone number format. Use Zimbabwe format (07xxxxxxxx)"
# #         )
    
# #     # Normalize phone number
# #     phone = payment_request.phone_number
# #     if phone.startswith("+263"):
# #         phone = "0" + phone[4:]
# #     elif phone.startswith("263"):
# #         phone = "0" + phone[3:]
    
# #     # Get order with items
# #     result = await db.execute(
# #         select(Order)
# #         .options(selectinload(Order.order_items))
# #         .where(
# #             and_(
# #                 Order.id == payment_request.order_id,
# #                 Order.user_id == current_user.id
# #             )
# #         )
# #     )
# #     order = result.scalar_one_or_none()
    
# #     if not order:
# #         raise HTTPException(
# #             status_code=status.HTTP_404_NOT_FOUND,
# #             detail="Order not found"
# #         )
    
# #     if order.payment_status == "paid":
# #         raise HTTPException(
# #             status_code=status.HTTP_400_BAD_REQUEST,
# #             detail="Order is already paid"
# #         )
    
# #     if not order.order_items:
# #         raise HTTPException(
# #             status_code=status.HTTP_400_BAD_REQUEST,
# #             detail="Order has no items"
# #         )
    
# #     # Determine amount based on currency
# #     if payment_request.currency.upper() == "ZWL":
# #         amount = float(convert_to_zwl(order.total_amount))
# #         paynow = get_paynow_client("ZWL")
# #     else:
# #         amount = float(order.total_amount)
# #         paynow = get_paynow_client("USD")
    
# #     # Create payment reference
# #     reference = f"Order#{order.order_number}"
    
# #     try:
# #         # Create Paynow payment
# #         payment = paynow.create_payment(reference, current_user.email)
        
# #         # Add items to payment
# #         for item in order.order_items:
# #             item_name = f"{item.product_name} x{item.quantity}"
# #             item_amount = float(item.unit_price * item.quantity)
# #             if payment_request.currency.upper() == "ZWL":
# #                 item_amount = float(convert_to_zwl(item.unit_price * item.quantity))
# #             payment.add(item_name, item_amount)
        
# #         # Add shipping if applicable
# #         if order.shipping_cost > 0:
# #             shipping_amount = float(order.shipping_cost)
# #             if payment_request.currency.upper() == "ZWL":
# #                 shipping_amount = float(convert_to_zwl(order.shipping_cost))
# #             payment.add("Shipping", shipping_amount)
        
# #         # Add tax if applicable
# #         if order.tax_amount > 0:
# #             tax_amount = float(order.tax_amount)
# #             if payment_request.currency.upper() == "ZWL":
# #                 tax_amount = float(convert_to_zwl(order.tax_amount))
# #             payment.add("Tax", tax_amount)
        
# #         # Apply discount if applicable
# #         if order.discount_amount > 0:
# #             discount_amount = -float(order.discount_amount)
# #             if payment_request.currency.upper() == "ZWL":
# #                 discount_amount = -float(convert_to_zwl(order.discount_amount))
# #             payment.add("Discount", discount_amount)
        
# #         # Send mobile payment
# #         response = paynow.send_mobile(payment, phone, payment_request.payment_method.lower())
        
# #         if response.success:
# #             # Create or update payment record
# #             payment_result = await db.execute(
# #                 select(Payment).where(Payment.order_id == order.id)
# #             )
# #             payment_record = payment_result.scalar_one_or_none()
            
# #             if not payment_record:
# #                 payment_record = Payment(
# #                     order_id=order.id,
# #                     payment_method=payment_request.payment_method,
# #                     amount=Decimal(str(amount)),
# #                     currency=payment_request.currency.upper(),
# #                     status="pending"
# #                 )
# #                 db.add(payment_record)
            
# #             # Update payment record
# #             payment_record.transaction_id = reference
# #             payment_record.gateway_response = response.poll_url
# #             payment_record.status = "pending"
            
# #             # Update order status
# #             order.payment_status = "pending"
            
# #             await db.commit()
# #             await db.refresh(payment_record)
            
# #             # Start background task to check payment status
# #             background_tasks.add_task(
# #                 check_payment_status_background,
# #                 response.poll_url,
# #                 payment_record.id,
# #                 db,
# #                 payment_request.currency.upper()
# #             )
            
# #             logger.info(f"Payment initiated for order {order.id}: {response.poll_url}")
            
# #             return PaynowPaymentResponse(
# #                 success=True,
# #                 poll_url=response.poll_url,
# #                 payment_id=reference,
# #                 status="sent",
# #                 message="Payment request sent! Please check your phone and enter your PIN to complete the payment. You have 5 minutes to confirm."
# #             )
# #         else:
# #             # Get error message
# #             error_message = response.error if hasattr(response, 'error') else "Payment initiation failed"
# #             logger.error(f"Paynow error for order {order.id}: {error_message}")
            
# #             raise HTTPException(
# #                 status_code=status.HTTP_400_BAD_REQUEST,
# #                 detail=error_message
# #             )
            
# #     except Exception as e:
# #         logger.error(f"Payment failed for order {order.id}: {str(e)}")
# #         raise HTTPException(
# #             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# #             detail=f"Payment service error: {str(e)}"
# #         )

# # @router.get("/status/{order_id}", response_model=PaynowStatusResponse)
# # async def check_payment_status(
# #     order_id: int,
# #     current_user: User = Depends(get_current_active_user),
# #     db: AsyncSession = Depends(get_db)
# # ):
# #     """Check payment status for an order"""
    
# #     # Get payment record
# #     result = await db.execute(
# #         select(Payment).join(Order).where(
# #             and_(
# #                 Payment.order_id == order_id,
# #                 Order.user_id == current_user.id
# #             )
# #         )
# #     )
# #     payment = result.scalar_one_or_none()
    
# #     if not payment:
# #         raise HTTPException(
# #             status_code=status.HTTP_404_NOT_FOUND,
# #             detail="Payment not found"
# #         )
    
# #     # If we have a poll URL, check current status
# #     if payment.gateway_response:
# #         try:
# #             paynow = get_paynow_client(payment.currency or "USD")
# #             status_response = paynow.check_transaction_status(payment.gateway_response)
            
# #             # Update status based on response
# #             if status_response.paid:
# #                 if payment.status != "completed":
# #                     payment.status = "completed"
# #                     payment.processed_at = datetime.utcnow()
                    
# #                     # Update order
# #                     order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
# #                     order = order_result.scalar_one()
# #                     order.payment_status = "paid"
# #                     order.status = "confirmed"
                    
# #                     await db.commit()
                
# #                 status = "paid"
# #             elif status_response.status.lower() == "cancelled":
# #                 if payment.status != "failed":
# #                     payment.status = "failed"
                    
# #                     # Update order
# #                     order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
# #                     order = order_result.scalar_one()
# #                     order.payment_status = "failed"
                    
# #                     await db.commit()
                
# #                 status = "cancelled"
# #             else:
# #                 status = status_response.status.lower()
            
# #             return PaynowStatusResponse(
# #                 success=True,
# #                 status=status,
# #                 payment_id=payment.transaction_id,
# #                 amount=float(payment.amount),
# #                 currency=payment.currency,
# #                 reference=payment.transaction_id
# #             )
            
# #         except Exception as e:
# #             logger.error(f"Error checking payment status: {str(e)}")
    
# #     # Return stored status if can't check
# #     status_map = {
# #         "completed": "paid",
# #         "pending": "sent",
# #         "failed": "cancelled",
# #         "expired": "expired",
# #         "cancelled": "cancelled"
# #     }
    
# #     status_text = status_map.get(payment.status, payment.status)
    
# #     # Add descriptive message based on status
# #     messages = {
# #         "sent": "Payment request sent. Waiting for PIN confirmation.",
# #         "paid": "Payment completed successfully!",
# #         "cancelled": "Payment cancelled by user or insufficient funds.",
# #         "expired": "Payment expired. User did not complete the transaction."
# #     }
    
# #     return PaynowStatusResponse(
# #         success=True,
# #         status=status_text,
# #         payment_id=payment.transaction_id,
# #         amount=float(payment.amount),
# #         currency=payment.currency,
# #         reference=payment.transaction_id,
# #         message=messages.get(status_text, f"Payment status: {status_text}")
# #     )

# # @router.post("/cancel/{order_id}")
# # async def cancel_payment(
# #     order_id: int,
# #     current_user: User = Depends(get_current_active_user),
# #     db: AsyncSession = Depends(get_db)
# # ):
# #     """Cancel a pending payment"""
    
# #     # Get payment record
# #     result = await db.execute(
# #         select(Payment).join(Order).where(
# #             and_(
# #                 Payment.order_id == order_id,
# #                 Order.user_id == current_user.id
# #             )
# #         )
# #     )
# #     payment = result.scalar_one_or_none()
    
# #     if not payment:
# #         raise HTTPException(
# #             status_code=status.HTTP_404_NOT_FOUND,
# #             detail="Payment not found"
# #         )
    
# #     if payment.status == "completed":
# #         raise HTTPException(
# #             status_code=status.HTTP_400_BAD_REQUEST,
# #             detail="Cannot cancel completed payment"
# #         )
    
# #     # Update payment status
# #     payment.status = "cancelled"
    
# #     # Update order
# #     order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
# #     order = order_result.scalar_one()
# #     order.payment_status = "cancelled"
# #     order.status = "cancelled"
    
# #     await db.commit()
    
# #     return {
# #         "success": True,
# #         "message": "Payment cancelled successfully"
# #     }

# # # Test endpoint
# # @router.get("/test-config")
# # async def test_config():
# #     """Test endpoint to verify Paynow configuration"""
# #     return {
# #         "usd_config": {
# #             "integration_id": PAYNOW_CONFIGS["USD"]["integration_id"],
# #             "configured": bool(PAYNOW_CONFIGS["USD"]["integration_key"])
# #         },
# #         "zwl_config": {
# #             "integration_id": PAYNOW_CONFIGS["ZWL"]["integration_id"],
# #             "configured": bool(PAYNOW_CONFIGS["ZWL"]["integration_key"])
# #         },
# #         "conversion_rate": USD_TO_ZWL_RATE,
# #         "supported_methods": ["ecocash", "onemoney"]
# #     }

# # __all__ = ["router"]


# # # from typing import Optional, Dict, Any, List
# # # from fastapi import APIRouter, Depends, HTTPException, status, Request
# # # from sqlalchemy.ext.asyncio import AsyncSession
# # # from sqlalchemy import select, update, and_
# # # from sqlalchemy.orm import selectinload
# # # from pydantic import BaseModel, HttpUrl
# # # import httpx
# # # import hashlib
# # # import uuid
# # # import logging
# # # import os
# # # from datetime import datetime
# # # from decimal import Decimal

# # # from app.database import get_db
# # # from app.models.order import Order, OrderItem, Payment
# # # from app.models.user import User
# # # from app.api.deps import get_current_active_user

# # # # Configure logging
# # # logging.basicConfig(level=logging.INFO)
# # # logger = logging.getLogger(__name__)

# # # router = APIRouter(prefix="/paynow", tags=["Paynow Payment"])

# # # # Paynow Configuration
# # # PAYNOW_CONFIG = {
# # #     "integration_id": os.getenv("PAYNOW_INTEGRATION_ID", "21436"),
# # #     "integration_key": os.getenv("PAYNOW_INTEGRATION_KEY", "your-integration-key-here"),
# # #     "return_url": os.getenv("PAYNOW_RETURN_URL", "http://localhost:3000/payment-return"),
# # #     "result_url": os.getenv("PAYNOW_RESULT_URL", "http://localhost:8000/api/paynow/webhook"),
# # #     "paynow_url": "https://www.paynow.co.zw/interface/initiatetransaction",
# # #     "mobile_url": "https://www.paynow.co.zw/interface/remotetransaction"
# # # }

# # # # Pydantic Models
# # # class PaynowPaymentRequest(BaseModel):
# # #     order_id: int
# # #     payment_method: str  # ecocash, onemoney, telecash, innbucks, card
# # #     phone_number: Optional[str] = None
# # #     email: str
# # #     return_url: Optional[str] = None

# # # class PaynowPaymentResponse(BaseModel):
# # #     success: bool
# # #     payment_url: Optional[str] = None
# # #     poll_url: Optional[str] = None
# # #     payment_id: str
# # #     instructions: Optional[str] = None
# # #     error_message: Optional[str] = None

# # # class PaynowStatusResponse(BaseModel):
# # #     success: bool
# # #     status: str
# # #     payment_id: str
# # #     amount: float
# # #     reference: str
# # #     paynow_reference: str

# # # # Helper Functions
# # # def generate_paynow_hash(data: Dict[str, Any], integration_key: str) -> str:
# # #     """Generate hash for Paynow request verification - follows Paynow spec"""
# # #     # Sort the data by keys (excluding hash field)
# # #     sorted_data = {key: value for key, value in sorted(data.items()) if key.lower() != 'hash'}
    
# # #     # Create concatenated string (values only, no keys)
# # #     hash_string = ""
# # #     for key in sorted(sorted_data.keys()):
# # #         hash_string += str(sorted_data[key])
    
# # #     # Append integration key
# # #     hash_string += integration_key
    
# # #     # Generate SHA512 hash
# # #     return hashlib.sha512(hash_string.encode('utf-8')).hexdigest().upper()

# # # def verify_paynow_hash(data: Dict[str, Any], received_hash: str, integration_key: str) -> bool:
# # #     """Verify hash from Paynow response"""
# # #     expected_hash = generate_paynow_hash(data, integration_key)
# # #     return expected_hash == received_hash.upper()

# # # async def create_paynow_payment(
# # #     order: Order, 
# # #     order_items: List[OrderItem],
# # #     payment_method: str, 
# # #     phone_number: Optional[str], 
# # #     email: str,
# # #     return_url: Optional[str] = None
# # # ) -> Dict[str, Any]:
# # #     """Create payment with Paynow using proper API structure"""
    
# # #     # Generate unique reference
# # #     reference = f"ORDER-{order.id}-{uuid.uuid4().hex[:8].upper()}"
    
# # #     # Prepare base payment data following Paynow API spec
# # #     payment_data = {
# # #         "id": PAYNOW_CONFIG["integration_id"],
# # #         "reference": reference,
# # #         "additionalinfo": f"Order #{order.order_number}",
# # #         "returnurl": return_url or PAYNOW_CONFIG["return_url"],
# # #         "resulturl": PAYNOW_CONFIG["result_url"],
# # #         "authemail": email,
# # #         "status": "Message"
# # #     }
    
# # #     # Add order items to payment (this is how Paynow calculates total)
# # #     # Items are added as item1, item1amount, item2, item2amount, etc.
# # #     total_amount = Decimal('0.00')
    
# # #     for i, item in enumerate(order_items, 1):
# # #         item_total = item.unit_price * item.quantity
# # #         total_amount += item_total
        
# # #         payment_data[f"item{i}"] = f"{item.product_name} x{item.quantity}"
# # #         payment_data[f"item{i}amount"] = str(float(item_total))
    
# # #     # Add shipping and taxes as separate items if applicable
# # #     item_count = len(order_items) + 1
# # #     if order.shipping_cost > 0:
# # #         payment_data[f"item{item_count}"] = "Shipping"
# # #         payment_data[f"item{item_count}amount"] = str(float(order.shipping_cost))
# # #         total_amount += order.shipping_cost
# # #         item_count += 1
    
# # #     if order.tax_amount > 0:
# # #         payment_data[f"item{item_count}"] = "Tax"
# # #         payment_data[f"item{item_count}amount"] = str(float(order.tax_amount))
# # #         total_amount += order.tax_amount
# # #         item_count += 1
    
# # #     # Subtract discount if applicable
# # #     if order.discount_amount > 0:
# # #         payment_data[f"item{item_count}"] = "Discount"
# # #         payment_data[f"item{item_count}amount"] = str(float(-order.discount_amount))
# # #         total_amount -= order.discount_amount
    
# # #     # Determine URL and add mobile-specific fields
# # #     url = PAYNOW_CONFIG["paynow_url"]
    
# # #     if payment_method in ["ecocash", "onemoney", "telecash"] and phone_number:
# # #         url = PAYNOW_CONFIG["mobile_url"]
# # #         payment_data["phone"] = phone_number
# # #         payment_data["method"] = payment_method
    
# # #     # Generate hash (must be last)
# # #     payment_data["hash"] = generate_paynow_hash(payment_data, PAYNOW_CONFIG["integration_key"])
    
# # #     logger.info(f"Initiating Paynow payment: {reference} for ${total_amount}")
    
# # #     try:
# # #         async with httpx.AsyncClient(timeout=30.0) as client:
# # #             response = await client.post(
# # #                 url,
# # #                 data=payment_data,
# # #                 headers={"Content-Type": "application/x-www-form-urlencoded"}
# # #             )
            
# # #             logger.info(f"Paynow raw response: {response.text}")
            
# # #             # Parse response (Paynow returns key=value pairs separated by &)
# # #             response_lines = response.text.strip().split('&')
# # #             response_data = {}
            
# # #             for line in response_lines:
# # #                 if '=' in line:
# # #                     key, value = line.split('=', 1)
# # #                     # URL decode the value
# # #                     import urllib.parse
# # #                     response_data[key.lower()] = urllib.parse.unquote(value)
            
# # #             logger.info(f"Parsed Paynow response: {response_data}")
            
# # #             # Check if request was successful
# # #             if response_data.get('status', '').lower() == 'ok':
# # #                 return {
# # #                     "success": True,
# # #                     "payment_url": response_data.get('browserurl'),
# # #                     "poll_url": response_data.get('pollurl'),
# # #                     "payment_id": reference,
# # #                     "paynow_reference": response_data.get('paynowreference', ''),
# # #                     "instructions": response_data.get('instructions', ''),
# # #                 }
# # #             else:
# # #                 error_msg = response_data.get('error', 'Unknown payment initialization error')
# # #                 logger.error(f"Paynow error: {error_msg}")
# # #                 return {
# # #                     "success": False,
# # #                     "error_message": error_msg
# # #                 }
                
# # #     except Exception as e:
# # #         logger.error(f"Paynow request failed: {str(e)}")
# # #         return {
# # #             "success": False,
# # #             "error_message": f"Payment service temporarily unavailable: {str(e)}"
# # #         }

# # # async def check_paynow_payment_status(poll_url: str) -> Dict[str, Any]:
# # #     """Check payment status from Paynow"""
# # #     try:
# # #         async with httpx.AsyncClient(timeout=15.0) as client:
# # #             response = await client.post(poll_url)
            
# # #             # Parse response
# # #             response_lines = response.text.strip().split('&')
# # #             response_data = {}
            
# # #             for line in response_lines:
# # #                 if '=' in line:
# # #                     key, value = line.split('=', 1)
# # #                     import urllib.parse
# # #                     response_data[key.lower()] = urllib.parse.unquote(value)
            
# # #             logger.info(f"Payment status response: {response_data}")
            
# # #             return {
# # #                 "success": True,
# # #                 "status": response_data.get('status', 'unknown'),
# # #                 "amount": float(response_data.get('amount', '0')),
# # #                 "reference": response_data.get('reference', ''),
# # #                 "paynow_reference": response_data.get('paynowreference', ''),
# # #                 "hash": response_data.get('hash', '')
# # #             }
            
# # #     except Exception as e:
# # #         logger.error(f"Payment status check failed: {str(e)}")
# # #         return {
# # #             "success": False,
# # #             "error_message": str(e)
# # #         }

# # # # API Endpoints
# # # @router.post("/initiate", response_model=PaynowPaymentResponse)
# # # async def initiate_payment(
# # #     payment_request: PaynowPaymentRequest,
# # #     current_user: User = Depends(get_current_active_user),
# # #     db: AsyncSession = Depends(get_db)
# # # ):
# # #     """Initiate Paynow payment for an order"""
    
# # #     # Get order with items
# # #     result = await db.execute(
# # #         select(Order)
# # #         .options(selectinload(Order.order_items))
# # #         .where(
# # #             and_(
# # #                 Order.id == payment_request.order_id,
# # #                 Order.user_id == current_user.id
# # #             )
# # #         )
# # #     )
# # #     order = result.scalar_one_or_none()
    
# # #     if not order:
# # #         raise HTTPException(
# # #             status_code=status.HTTP_404_NOT_FOUND,
# # #             detail="Order not found"
# # #         )
    
# # #     if order.payment_status == "paid":
# # #         raise HTTPException(
# # #             status_code=status.HTTP_400_BAD_REQUEST,
# # #             detail="Order is already paid"
# # #         )
    
# # #     if not order.order_items:
# # #         raise HTTPException(
# # #             status_code=status.HTTP_400_BAD_REQUEST,
# # #             detail="Order has no items"
# # #         )
    
# # #     # Create Paynow payment
# # #     paynow_result = await create_paynow_payment(
# # #         order=order,
# # #         order_items=order.order_items,
# # #         payment_method=payment_request.payment_method,
# # #         phone_number=payment_request.phone_number,
# # #         email=payment_request.email,
# # #         return_url=payment_request.return_url
# # #     )
    
# # #     if not paynow_result["success"]:
# # #         raise HTTPException(
# # #             status_code=status.HTTP_400_BAD_REQUEST,
# # #             detail=paynow_result["error_message"]
# # #         )
    
# # #     # Create or update payment record
# # #     payment_result = await db.execute(
# # #         select(Payment).where(Payment.order_id == order.id)
# # #     )
# # #     payment = payment_result.scalar_one_or_none()
    
# # #     if not payment:
# # #         payment = Payment(
# # #             order_id=order.id,
# # #             payment_method=payment_request.payment_method,
# # #             amount=order.total_amount,
# # #             currency="USD",
# # #             status="pending"
# # #         )
# # #         db.add(payment)
    
# # #     # Update payment with Paynow details
# # #     payment.transaction_id = paynow_result["payment_id"]
# # #     payment.gateway_response = str(paynow_result)
# # #     payment.status = "pending"
    
# # #     # Update order status
# # #     order.payment_status = "pending"
    
# # #     await db.commit()
# # #     await db.refresh(payment)
    
# # #     return PaynowPaymentResponse(
# # #         success=True,
# # #         payment_url=paynow_result.get("payment_url"),
# # #         poll_url=paynow_result.get("poll_url"),
# # #         payment_id=paynow_result["payment_id"],
# # #         instructions=paynow_result.get("instructions")
# # #     )

# # # @router.get("/status/{payment_id}", response_model=PaynowStatusResponse)
# # # async def check_payment_status(
# # #     payment_id: str,
# # #     current_user: User = Depends(get_current_active_user),
# # #     db: AsyncSession = Depends(get_db)
# # # ):
# # #     """Check payment status"""
    
# # #     # Get payment record
# # #     result = await db.execute(
# # #         select(Payment).join(Order).where(
# # #             and_(
# # #                 Payment.transaction_id == payment_id,
# # #                 Order.user_id == current_user.id
# # #             )
# # #         )
# # #     )
# # #     payment = result.scalar_one_or_none()
    
# # #     if not payment:
# # #         raise HTTPException(
# # #             status_code=status.HTTP_404_NOT_FOUND,
# # #             detail="Payment not found"
# # #         )
    
# # #     # Extract poll URL from gateway response
# # #     try:
# # #         gateway_response = eval(payment.gateway_response) if payment.gateway_response else {}
# # #         poll_url = gateway_response.get("poll_url")
# # #     except:
# # #         poll_url = None
    
# # #     if not poll_url:
# # #         # Return current status if no poll URL
# # #         return PaynowStatusResponse(
# # #             success=True,
# # #             status=payment.status,
# # #             payment_id=payment_id,
# # #             amount=float(payment.amount),
# # #             reference=payment_id,
# # #             paynow_reference=""
# # #         )
    
# # #     # Check status from Paynow
# # #     status_result = await check_paynow_payment_status(poll_url)
    
# # #     if not status_result["success"]:
# # #         raise HTTPException(
# # #             status_code=status.HTTP_400_BAD_REQUEST,
# # #             detail=status_result["error_message"]
# # #         )
    
# # #     # Update payment status if changed
# # #     paynow_status = status_result["status"].lower()
    
# # #     if paynow_status == "paid":
# # #         payment.status = "completed"
# # #         payment.processed_at = datetime.utcnow()
        
# # #         # Update order
# # #         order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
# # #         order = order_result.scalar_one()
# # #         order.payment_status = "paid"
# # #         order.status = "confirmed"
        
# # #     elif paynow_status in ["cancelled", "failed"]:
# # #         payment.status = "failed"
        
# # #         # Update order
# # #         order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
# # #         order = order_result.scalar_one()
# # #         order.payment_status = "failed"
    
# # #     await db.commit()
    
# # #     return PaynowStatusResponse(
# # #         success=True,
# # #         status=paynow_status,
# # #         payment_id=payment_id,
# # #         amount=status_result["amount"],
# # #         reference=status_result["reference"],
# # #         paynow_reference=status_result["paynow_reference"]
# # #     )

# # # @router.post("/webhook")
# # # async def paynow_webhook(
# # #     request: Request,
# # #     db: AsyncSession = Depends(get_db)
# # # ):
# # #     """Handle Paynow webhook notifications"""
    
# # #     try:
# # #         # Get form data
# # #         form_data = await request.form()
# # #         webhook_data = dict(form_data)
        
# # #         logger.info(f"Received Paynow webhook: {webhook_data}")
        
# # #         # Extract hash and verify
# # #         received_hash = webhook_data.pop('hash', '')
# # #         if not verify_paynow_hash(webhook_data, received_hash, PAYNOW_CONFIG["integration_key"]):
# # #             logger.error("Invalid webhook hash")
# # #             raise HTTPException(
# # #                 status_code=status.HTTP_400_BAD_REQUEST,
# # #                 detail="Invalid hash"
# # #             )
        
# # #         reference = webhook_data.get('reference')
# # #         paynow_status = webhook_data.get('status', '').lower()
        
# # #         # Find payment by reference
# # #         result = await db.execute(
# # #             select(Payment).where(Payment.transaction_id == reference)
# # #         )
# # #         payment = result.scalar_one_or_none()
        
# # #         if not payment:
# # #             logger.error(f"Payment not found for reference: {reference}")
# # #             return {"status": "payment not found"}
        
# # #         # Update payment status
# # #         if paynow_status == "paid":
# # #             payment.status = "completed"
# # #             payment.processed_at = datetime.utcnow()
            
# # #             # Update order
# # #             order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
# # #             order = order_result.scalar_one()
# # #             order.payment_status = "paid"
# # #             order.status = "confirmed"
            
# # #             logger.info(f"Payment completed for order {order.id}")
            
# # #         elif paynow_status in ["cancelled", "failed"]:
# # #             payment.status = "failed"
            
# # #             # Update order
# # #             order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
# # #             order = order_result.scalar_one()
# # #             order.payment_status = "failed"
            
# # #             logger.info(f"Payment failed for order {order.id}")
        
# # #         await db.commit()
        
# # #         return {"status": "ok"}
        
# # #     except Exception as e:
# # #         logger.error(f"Webhook processing failed: {str(e)}")
# # #         raise HTTPException(
# # #             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# # #             detail="Webhook processing failed"
# # #         )

# # # @router.get("/return")
# # # async def payment_return(
# # #     request: Request,
# # #     db: AsyncSession = Depends(get_db)
# # # ):
# # #     """Handle return from Paynow payment page"""
    
# # #     query_params = dict(request.query_params)
# # #     reference = query_params.get('reference')
    
# # #     if not reference:
# # #         raise HTTPException(
# # #             status_code=status.HTTP_400_BAD_REQUEST,
# # #             detail="Missing payment reference"
# # #         )
    
# # #     # Find payment
# # #     result = await db.execute(
# # #         select(Payment).join(Order).where(Payment.transaction_id == reference)
# # #     )
# # #     payment = result.scalar_one_or_none()
    
# # #     if not payment:
# # #         raise HTTPException(
# # #             status_code=status.HTTP_404_NOT_FOUND,
# # #             detail="Payment not found"
# # #         )
    
# # #     # Return order details for frontend to handle
# # #     return {
# # #         "order_id": payment.order_id,
# # #         "payment_status": payment.status,
# # #         "reference": reference,
# # #         "redirect_url": f"/order-confirmation/{payment.order_id}"
# # #     }

# # # # Test endpoint to verify configuration
# # # @router.get("/test-config")
# # # async def test_config():
# # #     """Test endpoint to verify Paynow configuration"""
# # #     return {
# # #         "integration_id": PAYNOW_CONFIG["integration_id"],
# # #         "return_url": PAYNOW_CONFIG["return_url"],
# # #         "result_url": PAYNOW_CONFIG["result_url"],
# # #         "paynow_url": PAYNOW_CONFIG["paynow_url"],
# # #         "mobile_url": PAYNOW_CONFIG["mobile_url"],
# # #         "integration_key_set": bool(PAYNOW_CONFIG["integration_key"] and PAYNOW_CONFIG["integration_key"] != "your-integration-key-here")
# # #     }

# # # # Test payment creation
# # # @router.post("/test-payment")
# # # async def test_payment(
# # #     current_user: User = Depends(get_current_active_user),
# # #     db: AsyncSession = Depends(get_db)
# # # ):
# # #     """Test payment creation with sample data"""
    
# # #     # Create a test payment structure
# # #     test_data = {
# # #         "id": PAYNOW_CONFIG["integration_id"],
# # #         "reference": f"TEST-{uuid.uuid4().hex[:8].upper()}",
# # #         "item1": "Test Product",
# # #         "item1amount": "10.00",
# # #         "additionalinfo": "Test payment",
# # #         "returnurl": PAYNOW_CONFIG["return_url"],
# # #         "resulturl": PAYNOW_CONFIG["result_url"],
# # #         "authemail": "test@example.com",
# # #         "status": "Message"
# # #     }
    
# # #     # Generate hash
# # #     test_hash = generate_paynow_hash(test_data, PAYNOW_CONFIG["integration_key"])
# # #     test_data["hash"] = test_hash
    
# # #     return {
# # #         "test_data": test_data,
# # #         "hash_generated": test_hash,
# # #         "ready_for_paynow": True
# # #     }

# # # __all__ = ["router"]


# # # # from typing import Optional, Dict, Any
# # # # from fastapi import APIRouter, Depends, HTTPException, status, Request
# # # # from sqlalchemy.ext.asyncio import AsyncSession
# # # # from sqlalchemy import select, update, and_
# # # # from pydantic import BaseModel, HttpUrl
# # # # import httpx
# # # # import hashlib
# # # # import uuid
# # # # import logging
# # # # import os
# # # # from datetime import datetime

# # # # from app.database import get_db
# # # # from app.models.order import Order, Payment
# # # # from app.models.user import User
# # # # from app.api.deps import get_current_active_user

# # # # # Configure logging
# # # # logging.basicConfig(level=logging.INFO)
# # # # logger = logging.getLogger(__name__)

# # # # router = APIRouter(prefix="/paynow", tags=["Paynow Payment"])

# # # # # Paynow Configuration - Direct from environment variables
# # # # PAYNOW_CONFIG = {
# # # #     "integration_id": os.getenv("PAYNOW_INTEGRATION_ID", "21436"),  # Your integration ID
# # # #     "integration_key": os.getenv("PAYNOW_INTEGRATION_KEY", "your-integration-key-here"),  # Your integration key
# # # #     "return_url": os.getenv("PAYNOW_RETURN_URL", "http://localhost:3000/payment-return"),
# # # #     "result_url": os.getenv("PAYNOW_RESULT_URL", "http://localhost:8000/api/paynow/webhook"),
# # # #     "paynow_url": "https://www.paynow.co.zw/interface/initiatetransaction"  # Use production URL
# # # # }

# # # # # Pydantic Models
# # # # class PaynowPaymentRequest(BaseModel):
# # # #     order_id: int
# # # #     payment_method: str  # ecocash, onemoney, innbucks, etc.
# # # #     phone_number: Optional[str] = None
# # # #     email: str
# # # #     return_url: Optional[str] = None

# # # # class PaynowPaymentResponse(BaseModel):
# # # #     success: bool
# # # #     payment_url: Optional[str] = None
# # # #     poll_url: Optional[str] = None
# # # #     payment_id: str
# # # #     instructions: Optional[str] = None
# # # #     error_message: Optional[str] = None

# # # # class PaynowStatusResponse(BaseModel):
# # # #     success: bool
# # # #     status: str  # paid, awaiting_delivery, delivered, cancelled, etc.
# # # #     payment_id: str
# # # #     amount: float
# # # #     reference: str
# # # #     paynow_reference: str

# # # # # Helper Functions
# # # # def generate_paynow_hash(data: Dict[str, Any], integration_key: str) -> str:
# # # #     """Generate hash for Paynow request verification"""
# # # #     # Sort the data by keys and create query string
# # # #     sorted_data = dict(sorted(data.items()))
# # # #     query_string = "&".join([f"{key}={value}" for key, value in sorted_data.items()])
# # # #     query_string += integration_key
    
# # # #     # Generate SHA512 hash
# # # #     return hashlib.sha512(query_string.encode('utf-8')).hexdigest().upper()

# # # # def verify_paynow_hash(data: Dict[str, Any], received_hash: str, integration_key: str) -> bool:
# # # #     """Verify hash from Paynow response"""
# # # #     expected_hash = generate_paynow_hash(data, integration_key)
# # # #     return expected_hash == received_hash.upper()

# # # # async def create_paynow_payment(
# # # #     order: Order, 
# # # #     payment_method: str, 
# # # #     phone_number: Optional[str], 
# # # #     email: str,
# # # #     return_url: Optional[str] = None
# # # # ) -> Dict[str, Any]:
# # # #     """Create payment with Paynow"""
    
# # # #     # Generate unique reference
# # # #     reference = f"ORDER-{order.id}-{uuid.uuid4().hex[:8].upper()}"
    
# # # #     # Prepare payment data
# # # #     payment_data = {
# # # #         "id": PAYNOW_CONFIG["integration_id"],
# # # #         "reference": reference,
# # # #         "amount": str(float(order.total_amount)),  # Ensure it's a string
# # # #         "additionalinfo": f"Order #{order.order_number}",
# # # #         "returnurl": return_url or PAYNOW_CONFIG["return_url"],
# # # #         "resulturl": PAYNOW_CONFIG["result_url"],
# # # #         "authemail": email,
# # # #         "status": "Message"
# # # #     }
    
# # # #     # Add phone number for mobile money payments
# # # #     if phone_number and payment_method in ["ecocash", "onemoney", "telecash"]:
# # # #         payment_data["phone"] = phone_number
    
# # # #     # Add payment method
# # # #     if payment_method == "ecocash":
# # # #         payment_data["method"] = "ecocash"
# # # #     elif payment_method == "onemoney":
# # # #         payment_data["method"] = "onemoney"
# # # #     elif payment_method == "telecash":
# # # #         payment_data["method"] = "telecash"
# # # #     elif payment_method == "innbucks":
# # # #         payment_data["method"] = "innbucks"
# # # #     # For card payments, don't specify method to show all options
    
# # # #     # Generate hash
# # # #     payment_data["hash"] = generate_paynow_hash(payment_data, PAYNOW_CONFIG["integration_key"])
    
# # # #     try:
# # # #         async with httpx.AsyncClient(timeout=30.0) as client:
# # # #             response = await client.post(
# # # #                 PAYNOW_CONFIG["paynow_url"],
# # # #                 data=payment_data,
# # # #                 headers={"Content-Type": "application/x-www-form-urlencoded"}
# # # #             )
            
# # # #             # Parse response
# # # #             response_lines = response.text.strip().split('\n')
# # # #             response_data = {}
            
# # # #             for line in response_lines:
# # # #                 if '=' in line:
# # # #                     key, value = line.split('=', 1)
# # # #                     response_data[key.lower()] = value
            
# # # #             logger.info(f"Paynow response: {response_data}")
            
# # # #             if response_data.get('status') == 'Ok':
# # # #                 return {
# # # #                     "success": True,
# # # #                     "payment_url": response_data.get('browserurl'),
# # # #                     "poll_url": response_data.get('pollurl'),
# # # #                     "payment_id": reference,
# # # #                     "paynow_reference": response_data.get('paynowreference'),
# # # #                     "instructions": response_data.get('instructions', ''),
# # # #                 }
# # # #             else:
# # # #                 error_msg = response_data.get('error', 'Unknown payment initialization error')
# # # #                 logger.error(f"Paynow error: {error_msg}")
# # # #                 return {
# # # #                     "success": False,
# # # #                     "error_message": error_msg
# # # #                 }
                
# # # #     except Exception as e:
# # # #         logger.error(f"Paynow request failed: {str(e)}")
# # # #         return {
# # # #             "success": False,
# # # #             "error_message": f"Payment service temporarily unavailable: {str(e)}"
# # # #         }

# # # # async def check_paynow_payment_status(poll_url: str) -> Dict[str, Any]:
# # # #     """Check payment status from Paynow"""
# # # #     try:
# # # #         async with httpx.AsyncClient(timeout=15.0) as client:
# # # #             response = await client.post(poll_url)
            
# # # #             # Parse response
# # # #             response_lines = response.text.strip().split('\n')
# # # #             response_data = {}
            
# # # #             for line in response_lines:
# # # #                 if '=' in line:
# # # #                     key, value = line.split('=', 1)
# # # #                     response_data[key.lower()] = value
            
# # # #             return {
# # # #                 "success": True,
# # # #                 "status": response_data.get('status', 'unknown'),
# # # #                 "amount": float(response_data.get('amount', '0')),
# # # #                 "reference": response_data.get('reference', ''),
# # # #                 "paynow_reference": response_data.get('paynowreference', ''),
# # # #                 "hash": response_data.get('hash', '')
# # # #             }
            
# # # #     except Exception as e:
# # # #         logger.error(f"Payment status check failed: {str(e)}")
# # # #         return {
# # # #             "success": False,
# # # #             "error_message": str(e)
# # # #         }

# # # # # API Endpoints
# # # # @router.post("/initiate", response_model=PaynowPaymentResponse)
# # # # async def initiate_payment(
# # # #     payment_request: PaynowPaymentRequest,
# # # #     current_user: User = Depends(get_current_active_user),
# # # #     db: AsyncSession = Depends(get_db)
# # # # ):
# # # #     """Initiate Paynow payment for an order"""
    
# # # #     # Get order
# # # #     result = await db.execute(
# # # #         select(Order).where(
# # # #             and_(
# # # #                 Order.id == payment_request.order_id,
# # # #                 Order.user_id == current_user.id
# # # #             )
# # # #         )
# # # #     )
# # # #     order = result.scalar_one_or_none()
    
# # # #     if not order:
# # # #         raise HTTPException(
# # # #             status_code=status.HTTP_404_NOT_FOUND,
# # # #             detail="Order not found"
# # # #         )
    
# # # #     if order.payment_status == "paid":
# # # #         raise HTTPException(
# # # #             status_code=status.HTTP_400_BAD_REQUEST,
# # # #             detail="Order is already paid"
# # # #         )
    
# # # #     # Create Paynow payment
# # # #     paynow_result = await create_paynow_payment(
# # # #         order=order,
# # # #         payment_method=payment_request.payment_method,
# # # #         phone_number=payment_request.phone_number,
# # # #         email=payment_request.email,
# # # #         return_url=payment_request.return_url
# # # #     )
    
# # # #     if not paynow_result["success"]:
# # # #         raise HTTPException(
# # # #             status_code=status.HTTP_400_BAD_REQUEST,
# # # #             detail=paynow_result["error_message"]
# # # #         )
    
# # # #     # Create or update payment record
# # # #     payment_result = await db.execute(
# # # #         select(Payment).where(Payment.order_id == order.id)
# # # #     )
# # # #     payment = payment_result.scalar_one_or_none()
    
# # # #     if not payment:
# # # #         payment = Payment(
# # # #             order_id=order.id,
# # # #             payment_method=payment_request.payment_method,
# # # #             amount=order.total_amount,
# # # #             currency="USD",
# # # #             status="pending"
# # # #         )
# # # #         db.add(payment)
    
# # # #     # Update payment with Paynow details
# # # #     payment.transaction_id = paynow_result["payment_id"]
# # # #     payment.gateway_response = str(paynow_result)
# # # #     payment.status = "pending"
    
# # # #     # Update order status
# # # #     order.payment_status = "pending"
    
# # # #     await db.commit()
# # # #     await db.refresh(payment)
    
# # # #     return PaynowPaymentResponse(
# # # #         success=True,
# # # #         payment_url=paynow_result.get("payment_url"),
# # # #         poll_url=paynow_result.get("poll_url"),
# # # #         payment_id=paynow_result["payment_id"],
# # # #         instructions=paynow_result.get("instructions")
# # # #     )

# # # # @router.get("/status/{payment_id}", response_model=PaynowStatusResponse)
# # # # async def check_payment_status(
# # # #     payment_id: str,
# # # #     current_user: User = Depends(get_current_active_user),
# # # #     db: AsyncSession = Depends(get_db)
# # # # ):
# # # #     """Check payment status"""
    
# # # #     # Get payment record
# # # #     result = await db.execute(
# # # #         select(Payment).join(Order).where(
# # # #             and_(
# # # #                 Payment.transaction_id == payment_id,
# # # #                 Order.user_id == current_user.id
# # # #             )
# # # #         )
# # # #     )
# # # #     payment = result.scalar_one_or_none()
    
# # # #     if not payment:
# # # #         raise HTTPException(
# # # #             status_code=status.HTTP_404_NOT_FOUND,
# # # #             detail="Payment not found"
# # # #         )
    
# # # #     # Extract poll URL from gateway response
# # # #     try:
# # # #         gateway_response = eval(payment.gateway_response) if payment.gateway_response else {}
# # # #         poll_url = gateway_response.get("poll_url")
# # # #     except:
# # # #         poll_url = None
    
# # # #     if not poll_url:
# # # #         # Return current status if no poll URL
# # # #         return PaynowStatusResponse(
# # # #             success=True,
# # # #             status=payment.status,
# # # #             payment_id=payment_id,
# # # #             amount=float(payment.amount),
# # # #             reference=payment_id,
# # # #             paynow_reference=""
# # # #         )
    
# # # #     # Check status from Paynow
# # # #     status_result = await check_paynow_payment_status(poll_url)
    
# # # #     if not status_result["success"]:
# # # #         raise HTTPException(
# # # #             status_code=status.HTTP_400_BAD_REQUEST,
# # # #             detail=status_result["error_message"]
# # # #         )
    
# # # #     # Update payment status if changed
# # # #     paynow_status = status_result["status"].lower()
    
# # # #     if paynow_status == "paid":
# # # #         payment.status = "completed"
# # # #         payment.processed_at = datetime.utcnow()
        
# # # #         # Update order
# # # #         order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
# # # #         order = order_result.scalar_one()
# # # #         order.payment_status = "paid"
# # # #         order.status = "confirmed"
        
# # # #     elif paynow_status in ["cancelled", "failed"]:
# # # #         payment.status = "failed"
        
# # # #         # Update order
# # # #         order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
# # # #         order = order_result.scalar_one()
# # # #         order.payment_status = "failed"
    
# # # #     await db.commit()
    
# # # #     return PaynowStatusResponse(
# # # #         success=True,
# # # #         status=paynow_status,
# # # #         payment_id=payment_id,
# # # #         amount=status_result["amount"],
# # # #         reference=status_result["reference"],
# # # #         paynow_reference=status_result["paynow_reference"]
# # # #     )

# # # # @router.post("/webhook")
# # # # async def paynow_webhook(
# # # #     request: Request,
# # # #     db: AsyncSession = Depends(get_db)
# # # # ):
# # # #     """Handle Paynow webhook notifications"""
    
# # # #     try:
# # # #         # Get form data
# # # #         form_data = await request.form()
# # # #         webhook_data = dict(form_data)
        
# # # #         logger.info(f"Received Paynow webhook: {webhook_data}")
        
# # # #         # Verify hash
# # # #         received_hash = webhook_data.pop('hash', '')
# # # #         if not verify_paynow_hash(webhook_data, received_hash, PAYNOW_CONFIG["integration_key"]):
# # # #             logger.error("Invalid webhook hash")
# # # #             raise HTTPException(
# # # #                 status_code=status.HTTP_400_BAD_REQUEST,
# # # #                 detail="Invalid hash"
# # # #             )
        
# # # #         reference = webhook_data.get('reference')
# # # #         paynow_status = webhook_data.get('status', '').lower()
        
# # # #         # Find payment by reference
# # # #         result = await db.execute(
# # # #             select(Payment).where(Payment.transaction_id == reference)
# # # #         )
# # # #         payment = result.scalar_one_or_none()
        
# # # #         if not payment:
# # # #             logger.error(f"Payment not found for reference: {reference}")
# # # #             return {"status": "payment not found"}
        
# # # #         # Update payment status
# # # #         if paynow_status == "paid":
# # # #             payment.status = "completed"
# # # #             payment.processed_at = datetime.utcnow()
            
# # # #             # Update order
# # # #             order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
# # # #             order = order_result.scalar_one()
# # # #             order.payment_status = "paid"
# # # #             order.status = "confirmed"
            
# # # #             logger.info(f"Payment completed for order {order.id}")
            
# # # #         elif paynow_status in ["cancelled", "failed"]:
# # # #             payment.status = "failed"
            
# # # #             # Update order
# # # #             order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
# # # #             order = order_result.scalar_one()
# # # #             order.payment_status = "failed"
            
# # # #             logger.info(f"Payment failed for order {order.id}")
        
# # # #         await db.commit()
        
# # # #         return {"status": "ok"}
        
# # # #     except Exception as e:
# # # #         logger.error(f"Webhook processing failed: {str(e)}")
# # # #         raise HTTPException(
# # # #             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# # # #             detail="Webhook processing failed"
# # # #         )

# # # # @router.get("/return")
# # # # async def payment_return(
# # # #     request: Request,
# # # #     db: AsyncSession = Depends(get_db)
# # # # ):
# # # #     """Handle return from Paynow payment page"""
    
# # # #     query_params = dict(request.query_params)
# # # #     reference = query_params.get('reference')
    
# # # #     if not reference:
# # # #         raise HTTPException(
# # # #             status_code=status.HTTP_400_BAD_REQUEST,
# # # #             detail="Missing payment reference"
# # # #         )
    
# # # #     # Find payment
# # # #     result = await db.execute(
# # # #         select(Payment).join(Order).where(Payment.transaction_id == reference)
# # # #     )
# # # #     payment = result.scalar_one_or_none()
    
# # # #     if not payment:
# # # #         raise HTTPException(
# # # #             status_code=status.HTTP_404_NOT_FOUND,
# # # #             detail="Payment not found"
# # # #         )
    
# # # #     # Return order details for frontend to handle
# # # #     return {
# # # #         "order_id": payment.order_id,
# # # #         "payment_status": payment.status,
# # # #         "reference": reference,
# # # #         "redirect_url": f"/order-confirmation/{payment.order_id}"
# # # #     }

# # # # # Test endpoint to verify configuration
# # # # @router.get("/test-config")
# # # # async def test_config():
# # # #     """Test endpoint to verify Paynow configuration"""
# # # #     return {
# # # #         "integration_id": PAYNOW_CONFIG["integration_id"],
# # # #         "return_url": PAYNOW_CONFIG["return_url"],
# # # #         "result_url": PAYNOW_CONFIG["result_url"],
# # # #         "paynow_url": PAYNOW_CONFIG["paynow_url"],
# # # #         "integration_key_set": bool(PAYNOW_CONFIG["integration_key"] and PAYNOW_CONFIG["integration_key"] != "your-integration-key-here")
# # # #     }

# # # # __all__ = ["router"]


# # # # # from typing import Optional, Dict, Any
# # # # # from fastapi import APIRouter, Depends, HTTPException, status, Request
# # # # # from sqlalchemy.ext.asyncio import AsyncSession
# # # # # from sqlalchemy import select, update, and_
# # # # # from pydantic import BaseModel, HttpUrl
# # # # # import httpx
# # # # # import hashlib
# # # # # import uuid
# # # # # import logging
# # # # # from datetime import datetime

# # # # # from app.database import get_db
# # # # # from app.models.order import Order, Payment
# # # # # from app.models.user import User
# # # # # from app.api.deps import get_current_active_user
# # # # # from app.config import settings

# # # # # # Configure logging
# # # # # logging.basicConfig(level=logging.INFO)
# # # # # logger = logging.getLogger(__name__)

# # # # # router = APIRouter(prefix="/paynow", tags=["Paynow Payment"])

# # # # # # Paynow Configuration
# # # # # PAYNOW_CONFIG = {
# # # # #     "integration_id": settings.PAYNOW_INTEGRATION_ID,  # Add to your settings
# # # # #     "integration_key": settings.PAYNOW_INTEGRATION_KEY,  # Add to your settings
# # # # #     "return_url": settings.PAYNOW_RETURN_URL,  # Add to your settings 
# # # # #     "result_url": settings.PAYNOW_RESULT_URL,  # Add to your settings
# # # # #     "paynow_url": "https://www.paynow.co.zw/interface/initiatetransaction"
# # # # # }

# # # # # # Pydantic Models
# # # # # class PaynowPaymentRequest(BaseModel):
# # # # #     order_id: int
# # # # #     payment_method: str  # ecocash, onemoney, innbucks, etc.
# # # # #     phone_number: Optional[str] = None
# # # # #     email: str
# # # # #     return_url: Optional[HttpUrl] = None

# # # # # class PaynowPaymentResponse(BaseModel):
# # # # #     success: bool
# # # # #     payment_url: Optional[str] = None
# # # # #     poll_url: Optional[str] = None
# # # # #     payment_id: str
# # # # #     instructions: Optional[str] = None
# # # # #     error_message: Optional[str] = None

# # # # # class PaynowStatusResponse(BaseModel):
# # # # #     success: bool
# # # # #     status: str  # paid, awaiting_delivery, delivered, cancelled, etc.
# # # # #     payment_id: str
# # # # #     amount: float
# # # # #     reference: str
# # # # #     paynow_reference: str

# # # # # class PaynowWebhookPayload(BaseModel):
# # # # #     reference: str
# # # # #     paynowreference: str
# # # # #     amount: str
# # # # #     status: str
# # # # #     pollurl: str
# # # # #     hash: str

# # # # # # Helper Functions
# # # # # def generate_paynow_hash(data: Dict[str, Any], integration_key: str) -> str:
# # # # #     """Generate hash for Paynow request verification"""
# # # # #     # Sort the data by keys and create query string
# # # # #     sorted_data = dict(sorted(data.items()))
# # # # #     query_string = "&".join([f"{key}={value}" for key, value in sorted_data.items()])
# # # # #     query_string += integration_key
    
# # # # #     # Generate SHA512 hash
# # # # #     return hashlib.sha512(query_string.encode('utf-8')).hexdigest().upper()

# # # # # def verify_paynow_hash(data: Dict[str, Any], received_hash: str, integration_key: str) -> bool:
# # # # #     """Verify hash from Paynow response"""
# # # # #     expected_hash = generate_paynow_hash(data, integration_key)
# # # # #     return expected_hash == received_hash.upper()

# # # # # async def create_paynow_payment(
# # # # #     order: Order, 
# # # # #     payment_method: str, 
# # # # #     phone_number: Optional[str], 
# # # # #     email: str,
# # # # #     return_url: Optional[str] = None
# # # # # ) -> Dict[str, Any]:
# # # # #     """Create payment with Paynow"""
    
# # # # #     # Generate unique reference
# # # # #     reference = f"ORDER-{order.id}-{uuid.uuid4().hex[:8].upper()}"
    
# # # # #     # Prepare payment data
# # # # #     payment_data = {
# # # # #         "id": PAYNOW_CONFIG["integration_id"],
# # # # #         "reference": reference,
# # # # #         "amount": str(order.total_amount),
# # # # #         "additionalinfo": f"Order #{order.order_number}",
# # # # #         "returnurl": return_url or PAYNOW_CONFIG["return_url"],
# # # # #         "resulturl": PAYNOW_CONFIG["result_url"],
# # # # #         "authemail": email,
# # # # #         "status": "Message"
# # # # #     }
    
# # # # #     # Add phone number for mobile money payments
# # # # #     if phone_number and payment_method in ["ecocash", "onemoney", "telecash"]:
# # # # #         payment_data["phone"] = phone_number
    
# # # # #     # Add payment method
# # # # #     if payment_method == "ecocash":
# # # # #         payment_data["method"] = "ecocash"
# # # # #     elif payment_method == "onemoney":
# # # # #         payment_data["method"] = "onemoney"
# # # # #     elif payment_method == "telecash":
# # # # #         payment_data["method"] = "telecash"
# # # # #     elif payment_method == "innbucks":
# # # # #         payment_data["method"] = "innbucks"
# # # # #     # For card payments, don't specify method to show all options
    
# # # # #     # Generate hash
# # # # #     payment_data["hash"] = generate_paynow_hash(payment_data, PAYNOW_CONFIG["integration_key"])
    
# # # # #     try:
# # # # #         async with httpx.AsyncClient(timeout=30.0) as client:
# # # # #             response = await client.post(
# # # # #                 PAYNOW_CONFIG["paynow_url"],
# # # # #                 data=payment_data,
# # # # #                 headers={"Content-Type": "application/x-www-form-urlencoded"}
# # # # #             )
            
# # # # #             # Parse response
# # # # #             response_lines = response.text.strip().split('\n')
# # # # #             response_data = {}
            
# # # # #             for line in response_lines:
# # # # #                 if '=' in line:
# # # # #                     key, value = line.split('=', 1)
# # # # #                     response_data[key.lower()] = value
            
# # # # #             logger.info(f"Paynow response: {response_data}")
            
# # # # #             if response_data.get('status') == 'Ok':
# # # # #                 return {
# # # # #                     "success": True,
# # # # #                     "payment_url": response_data.get('browserurl'),
# # # # #                     "poll_url": response_data.get('pollurl'),
# # # # #                     "payment_id": reference,
# # # # #                     "paynow_reference": response_data.get('paynowreference'),
# # # # #                     "instructions": response_data.get('instructions', ''),
# # # # #                 }
# # # # #             else:
# # # # #                 error_msg = response_data.get('error', 'Unknown payment initialization error')
# # # # #                 logger.error(f"Paynow error: {error_msg}")
# # # # #                 return {
# # # # #                     "success": False,
# # # # #                     "error_message": error_msg
# # # # #                 }
                
# # # # #     except Exception as e:
# # # # #         logger.error(f"Paynow request failed: {str(e)}")
# # # # #         return {
# # # # #             "success": False,
# # # # #             "error_message": f"Payment service temporarily unavailable: {str(e)}"
# # # # #         }

# # # # # async def check_paynow_payment_status(poll_url: str) -> Dict[str, Any]:
# # # # #     """Check payment status from Paynow"""
# # # # #     try:
# # # # #         async with httpx.AsyncClient(timeout=15.0) as client:
# # # # #             response = await client.post(poll_url)
            
# # # # #             # Parse response
# # # # #             response_lines = response.text.strip().split('\n')
# # # # #             response_data = {}
            
# # # # #             for line in response_lines:
# # # # #                 if '=' in line:
# # # # #                     key, value = line.split('=', 1)
# # # # #                     response_data[key.lower()] = value
            
# # # # #             return {
# # # # #                 "success": True,
# # # # #                 "status": response_data.get('status', 'unknown'),
# # # # #                 "amount": float(response_data.get('amount', '0')),
# # # # #                 "reference": response_data.get('reference', ''),
# # # # #                 "paynow_reference": response_data.get('paynowreference', ''),
# # # # #                 "hash": response_data.get('hash', '')
# # # # #             }
            
# # # # #     except Exception as e:
# # # # #         logger.error(f"Payment status check failed: {str(e)}")
# # # # #         return {
# # # # #             "success": False,
# # # # #             "error_message": str(e)
# # # # #         }

# # # # # # API Endpoints
# # # # # @router.post("/initiate", response_model=PaynowPaymentResponse)
# # # # # async def initiate_payment(
# # # # #     payment_request: PaynowPaymentRequest,
# # # # #     current_user: User = Depends(get_current_active_user),
# # # # #     db: AsyncSession = Depends(get_db)
# # # # # ):
# # # # #     """Initiate Paynow payment for an order"""
    
# # # # #     # Get order
# # # # #     result = await db.execute(
# # # # #         select(Order).where(
# # # # #             and_(
# # # # #                 Order.id == payment_request.order_id,
# # # # #                 Order.user_id == current_user.id
# # # # #             )
# # # # #         )
# # # # #     )
# # # # #     order = result.scalar_one_or_none()
    
# # # # #     if not order:
# # # # #         raise HTTPException(
# # # # #             status_code=status.HTTP_404_NOT_FOUND,
# # # # #             detail="Order not found"
# # # # #         )
    
# # # # #     if order.payment_status == "paid":
# # # # #         raise HTTPException(
# # # # #             status_code=status.HTTP_400_BAD_REQUEST,
# # # # #             detail="Order is already paid"
# # # # #         )
    
# # # # #     # Create Paynow payment
# # # # #     paynow_result = await create_paynow_payment(
# # # # #         order=order,
# # # # #         payment_method=payment_request.payment_method,
# # # # #         phone_number=payment_request.phone_number,
# # # # #         email=payment_request.email,
# # # # #         return_url=str(payment_request.return_url) if payment_request.return_url else None
# # # # #     )
    
# # # # #     if not paynow_result["success"]:
# # # # #         raise HTTPException(
# # # # #             status_code=status.HTTP_400_BAD_REQUEST,
# # # # #             detail=paynow_result["error_message"]
# # # # #         )
    
# # # # #     # Create or update payment record
# # # # #     payment_result = await db.execute(
# # # # #         select(Payment).where(Payment.order_id == order.id)
# # # # #     )
# # # # #     payment = payment_result.scalar_one_or_none()
    
# # # # #     if not payment:
# # # # #         payment = Payment(
# # # # #             order_id=order.id,
# # # # #             payment_method=payment_request.payment_method,
# # # # #             amount=order.total_amount,
# # # # #             currency="USD",
# # # # #             status="pending"
# # # # #         )
# # # # #         db.add(payment)
    
# # # # #     # Update payment with Paynow details
# # # # #     payment.transaction_id = paynow_result["payment_id"]
# # # # #     payment.gateway_response = str(paynow_result)
# # # # #     payment.status = "pending"
    
# # # # #     # Update order status
# # # # #     order.payment_status = "pending"
    
# # # # #     await db.commit()
# # # # #     await db.refresh(payment)
    
# # # # #     return PaynowPaymentResponse(
# # # # #         success=True,
# # # # #         payment_url=paynow_result.get("payment_url"),
# # # # #         poll_url=paynow_result.get("poll_url"),
# # # # #         payment_id=paynow_result["payment_id"],
# # # # #         instructions=paynow_result.get("instructions")
# # # # #     )

# # # # # @router.get("/status/{payment_id}", response_model=PaynowStatusResponse)
# # # # # async def check_payment_status(
# # # # #     payment_id: str,
# # # # #     current_user: User = Depends(get_current_active_user),
# # # # #     db: AsyncSession = Depends(get_db)
# # # # # ):
# # # # #     """Check payment status"""
    
# # # # #     # Get payment record
# # # # #     result = await db.execute(
# # # # #         select(Payment).join(Order).where(
# # # # #             and_(
# # # # #                 Payment.transaction_id == payment_id,
# # # # #                 Order.user_id == current_user.id
# # # # #             )
# # # # #         )
# # # # #     )
# # # # #     payment = result.scalar_one_or_none()
    
# # # # #     if not payment:
# # # # #         raise HTTPException(
# # # # #             status_code=status.HTTP_404_NOT_FOUND,
# # # # #             detail="Payment not found"
# # # # #         )
    
# # # # #     # Extract poll URL from gateway response
# # # # #     gateway_response = eval(payment.gateway_response) if payment.gateway_response else {}
# # # # #     poll_url = gateway_response.get("poll_url")
    
# # # # #     if not poll_url:
# # # # #         raise HTTPException(
# # # # #             status_code=status.HTTP_400_BAD_REQUEST,
# # # # #             detail="Unable to check payment status"
# # # # #         )
    
# # # # #     # Check status from Paynow
# # # # #     status_result = await check_paynow_payment_status(poll_url)
    
# # # # #     if not status_result["success"]:
# # # # #         raise HTTPException(
# # # # #             status_code=status.HTTP_400_BAD_REQUEST,
# # # # #             detail=status_result["error_message"]
# # # # #         )
    
# # # # #     # Update payment status if changed
# # # # #     paynow_status = status_result["status"].lower()
    
# # # # #     if paynow_status == "paid":
# # # # #         payment.status = "completed"
# # # # #         payment.processed_at = datetime.utcnow()
        
# # # # #         # Update order
# # # # #         order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
# # # # #         order = order_result.scalar_one()
# # # # #         order.payment_status = "paid"
# # # # #         order.status = "confirmed"
        
# # # # #     elif paynow_status in ["cancelled", "failed"]:
# # # # #         payment.status = "failed"
        
# # # # #         # Update order
# # # # #         order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
# # # # #         order = order_result.scalar_one()
# # # # #         order.payment_status = "failed"
    
# # # # #     await db.commit()
    
# # # # #     return PaynowStatusResponse(
# # # # #         success=True,
# # # # #         status=paynow_status,
# # # # #         payment_id=payment_id,
# # # # #         amount=status_result["amount"],
# # # # #         reference=status_result["reference"],
# # # # #         paynow_reference=status_result["paynow_reference"]
# # # # #     )

# # # # # @router.post("/webhook")
# # # # # async def paynow_webhook(
# # # # #     request: Request,
# # # # #     db: AsyncSession = Depends(get_db)
# # # # # ):
# # # # #     """Handle Paynow webhook notifications"""
    
# # # # #     try:
# # # # #         # Get form data
# # # # #         form_data = await request.form()
# # # # #         webhook_data = dict(form_data)
        
# # # # #         logger.info(f"Received Paynow webhook: {webhook_data}")
        
# # # # #         # Verify hash
# # # # #         received_hash = webhook_data.pop('hash', '')
# # # # #         if not verify_paynow_hash(webhook_data, received_hash, PAYNOW_CONFIG["integration_key"]):
# # # # #             logger.error("Invalid webhook hash")
# # # # #             raise HTTPException(
# # # # #                 status_code=status.HTTP_400_BAD_REQUEST,
# # # # #                 detail="Invalid hash"
# # # # #             )
        
# # # # #         reference = webhook_data.get('reference')
# # # # #         paynow_status = webhook_data.get('status', '').lower()
        
# # # # #         # Find payment by reference
# # # # #         result = await db.execute(
# # # # #             select(Payment).where(Payment.transaction_id == reference)
# # # # #         )
# # # # #         payment = result.scalar_one_or_none()
        
# # # # #         if not payment:
# # # # #             logger.error(f"Payment not found for reference: {reference}")
# # # # #             return {"status": "payment not found"}
        
# # # # #         # Update payment status
# # # # #         if paynow_status == "paid":
# # # # #             payment.status = "completed"
# # # # #             payment.processed_at = datetime.utcnow()
            
# # # # #             # Update order
# # # # #             order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
# # # # #             order = order_result.scalar_one()
# # # # #             order.payment_status = "paid"
# # # # #             order.status = "confirmed"
            
# # # # #             logger.info(f"Payment completed for order {order.id}")
            
# # # # #         elif paynow_status in ["cancelled", "failed"]:
# # # # #             payment.status = "failed"
            
# # # # #             # Update order
# # # # #             order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
# # # # #             order = order_result.scalar_one()
# # # # #             order.payment_status = "failed"
            
# # # # #             logger.info(f"Payment failed for order {order.id}")
        
# # # # #         await db.commit()
        
# # # # #         return {"status": "ok"}
        
# # # # #     except Exception as e:
# # # # #         logger.error(f"Webhook processing failed: {str(e)}")
# # # # #         raise HTTPException(
# # # # #             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# # # # #             detail="Webhook processing failed"
# # # # #         )

# # # # # @router.get("/return")
# # # # # async def payment_return(
# # # # #     request: Request,
# # # # #     db: AsyncSession = Depends(get_db)
# # # # # ):
# # # # #     """Handle return from Paynow payment page"""
    
# # # # #     query_params = dict(request.query_params)
# # # # #     reference = query_params.get('reference')
    
# # # # #     if not reference:
# # # # #         raise HTTPException(
# # # # #             status_code=status.HTTP_400_BAD_REQUEST,
# # # # #             detail="Missing payment reference"
# # # # #         )
    
# # # # #     # Find payment
# # # # #     result = await db.execute(
# # # # #         select(Payment).join(Order).where(Payment.transaction_id == reference)
# # # # #     )
# # # # #     payment = result.scalar_one_or_none()
    
# # # # #     if not payment:
# # # # #         raise HTTPException(
# # # # #             status_code=status.HTTP_404_NOT_FOUND,
# # # # #             detail="Payment not found"
# # # # #         )
    
# # # # #     # Return order details for frontend to handle
# # # # #     return {
# # # # #         "order_id": payment.order_id,
# # # # #         "payment_status": payment.status,
# # # # #         "reference": reference,
# # # # #         "redirect_url": f"/order-confirmation/{payment.order_id}"
# # # # #     }

# # # # # # Express Checkout for Mobile Money
# # # # # @router.post("/express", response_model=PaynowPaymentResponse)
# # # # # async def express_checkout(
# # # # #     payment_request: PaynowPaymentRequest,
# # # # #     current_user: User = Depends(get_current_active_user),
# # # # #     db: AsyncSession = Depends(get_db)
# # # # # ):
# # # # #     """Express checkout for mobile money payments (EcoCash, OneMoney, etc.)"""
    
# # # # #     if payment_request.payment_method not in ["ecocash", "onemoney", "telecash"]:
# # # # #         raise HTTPException(
# # # # #             status_code=status.HTTP_400_BAD_REQUEST,
# # # # #             detail="Express checkout only available for mobile money payments"
# # # # #         )
    
# # # # #     if not payment_request.phone_number:
# # # # #         raise HTTPException(
# # # # #             status_code=status.HTTP_400_BAD_REQUEST,
# # # # #             detail="Phone number is required for mobile money payments"
# # # # #         )
    
# # # # #     # Use the same initiate_payment logic but with express handling
# # # # #     return await initiate_payment(payment_request, current_user, db)

# # # # # __all__ = ["router"]

# # # # # # from typing import Optional, Dict, Any
# # # # # # from fastapi import APIRouter, Depends, HTTPException, status, Request
# # # # # # from sqlalchemy.ext.asyncio import AsyncSession
# # # # # # from sqlalchemy import select, update, and_
# # # # # # from pydantic import BaseModel, HttpUrl
# # # # # # import httpx
# # # # # # import hashlib
# # # # # # import uuid
# # # # # # import logging
# # # # # # from datetime import datetime

# # # # # # from app.database import get_db
# # # # # # from app.models.order import Order, Payment
# # # # # # from app.models.user import User
# # # # # # from app.api.deps import get_current_active_user
# # # # # # from app.config import settings

# # # # # # # Configure logging
# # # # # # logging.basicConfig(level=logging.INFO)
# # # # # # logger = logging.getLogger(__name__)

# # # # # # router = APIRouter(prefix="/paynow", tags=["Paynow Payment"])

# # # # # # # Paynow Configuration
# # # # # # PAYNOW_CONFIG = {
# # # # # #     "integration_id": settings.PAYNOW_INTEGRATION_ID,  # Add to your settings
# # # # # #     "integration_key": settings.PAYNOW_INTEGRATION_KEY,  # Add to your settings
# # # # # #     "return_url": settings.PAYNOW_RETURN_URL,  # Add to your settings 
# # # # # #     "result_url": settings.PAYNOW_RESULT_URL,  # Add to your settings
# # # # # #     "paynow_url": "https://www.paynow.co.zw/interface/initiatetransaction"
# # # # # # }

# # # # # # # Pydantic Models
# # # # # # class PaynowPaymentRequest(BaseModel):
# # # # # #     order_id: int
# # # # # #     payment_method: str  # ecocash, onemoney, innbucks, etc.
# # # # # #     phone_number: Optional[str] = None
# # # # # #     email: str
# # # # # #     return_url: Optional[HttpUrl] = None

# # # # # # class PaynowPaymentResponse(BaseModel):
# # # # # #     success: bool
# # # # # #     payment_url: Optional[str] = None
# # # # # #     poll_url: Optional[str] = None
# # # # # #     payment_id: str
# # # # # #     instructions: Optional[str] = None
# # # # # #     error_message: Optional[str] = None

# # # # # # class PaynowStatusResponse(BaseModel):
# # # # # #     success: bool
# # # # # #     status: str  # paid, awaiting_delivery, delivered, cancelled, etc.
# # # # # #     payment_id: str
# # # # # #     amount: float
# # # # # #     reference: str
# # # # # #     paynow_reference: str

# # # # # # class PaynowWebhookPayload(BaseModel):
# # # # # #     reference: str
# # # # # #     paynowreference: str
# # # # # #     amount: str
# # # # # #     status: str
# # # # # #     pollurl: str
# # # # # #     hash: str

# # # # # # # Helper Functions
# # # # # # def generate_paynow_hash(data: Dict[str, Any], integration_key: str) -> str:
# # # # # #     """Generate hash for Paynow request verification"""
# # # # # #     # Sort the data by keys and create query string
# # # # # #     sorted_data = dict(sorted(data.items()))
# # # # # #     query_string = "&".join([f"{key}={value}" for key, value in sorted_data.items()])
# # # # # #     query_string += integration_key
    
# # # # # #     # Generate SHA512 hash
# # # # # #     return hashlib.sha512(query_string.encode('utf-8')).hexdigest().upper()

# # # # # # def verify_paynow_hash(data: Dict[str, Any], received_hash: str, integration_key: str) -> bool:
# # # # # #     """Verify hash from Paynow response"""
# # # # # #     expected_hash = generate_paynow_hash(data, integration_key)
# # # # # #     return expected_hash == received_hash.upper()

# # # # # # async def create_paynow_payment(
# # # # # #     order: Order, 
# # # # # #     payment_method: str, 
# # # # # #     phone_number: Optional[str], 
# # # # # #     email: str,
# # # # # #     return_url: Optional[str] = None
# # # # # # ) -> Dict[str, Any]:
# # # # # #     """Create payment with Paynow"""
    
# # # # # #     # Generate unique reference
# # # # # #     reference = f"ORDER-{order.id}-{uuid.uuid4().hex[:8].upper()}"
    
# # # # # #     # Prepare payment data
# # # # # #     payment_data = {
# # # # # #         "id": PAYNOW_CONFIG["integration_id"],
# # # # # #         "reference": reference,
# # # # # #         "amount": str(order.total_amount),
# # # # # #         "additionalinfo": f"Order #{order.order_number}",
# # # # # #         "returnurl": return_url or PAYNOW_CONFIG["return_url"],
# # # # # #         "resulturl": PAYNOW_CONFIG["result_url"],
# # # # # #         "authemail": email,
# # # # # #         "status": "Message"
# # # # # #     }
    
# # # # # #     # Add phone number for mobile money payments
# # # # # #     if phone_number and payment_method in ["ecocash", "onemoney", "telecash"]:
# # # # # #         payment_data["phone"] = phone_number
    
# # # # # #     # Add payment method
# # # # # #     if payment_method == "ecocash":
# # # # # #         payment_data["method"] = "ecocash"
# # # # # #     elif payment_method == "onemoney":
# # # # # #         payment_data["method"] = "onemoney"
# # # # # #     elif payment_method == "telecash":
# # # # # #         payment_data["method"] = "telecash"
# # # # # #     elif payment_method == "innbucks":
# # # # # #         payment_data["method"] = "innbucks"
# # # # # #     # For card payments, don't specify method to show all options
    
# # # # # #     # Generate hash
# # # # # #     payment_data["hash"] = generate_paynow_hash(payment_data, PAYNOW_CONFIG["integration_key"])
    
# # # # # #     try:
# # # # # #         async with httpx.AsyncClient(timeout=30.0) as client:
# # # # # #             response = await client.post(
# # # # # #                 PAYNOW_CONFIG["paynow_url"],
# # # # # #                 data=payment_data,
# # # # # #                 headers={"Content-Type": "application/x-www-form-urlencoded"}
# # # # # #             )
            
# # # # # #             # Parse response
# # # # # #             response_lines = response.text.strip().split('\n')
# # # # # #             response_data = {}
            
# # # # # #             for line in response_lines:
# # # # # #                 if '=' in line:
# # # # # #                     key, value = line.split('=', 1)
# # # # # #                     response_data[key.lower()] = value
            
# # # # # #             logger.info(f"Paynow response: {response_data}")
            
# # # # # #             if response_data.get('status') == 'Ok':
# # # # # #                 return {
# # # # # #                     "success": True,
# # # # # #                     "payment_url": response_data.get('browserurl'),
# # # # # #                     "poll_url": response_data.get('pollurl'),
# # # # # #                     "payment_id": reference,
# # # # # #                     "paynow_reference": response_data.get('paynowreference'),
# # # # # #                     "instructions": response_data.get('instructions', ''),
# # # # # #                 }
# # # # # #             else:
# # # # # #                 error_msg = response_data.get('error', 'Unknown payment initialization error')
# # # # # #                 logger.error(f"Paynow error: {error_msg}")
# # # # # #                 return {
# # # # # #                     "success": False,
# # # # # #                     "error_message": error_msg
# # # # # #                 }
                
# # # # # #     except Exception as e:
# # # # # #         logger.error(f"Paynow request failed: {str(e)}")
# # # # # #         return {
# # # # # #             "success": False,
# # # # # #             "error_message": f"Payment service temporarily unavailable: {str(e)}"
# # # # # #         }

# # # # # # async def check_paynow_payment_status(poll_url: str) -> Dict[str, Any]:
# # # # # #     """Check payment status from Paynow"""
# # # # # #     try:
# # # # # #         async with httpx.AsyncClient(timeout=15.0) as client:
# # # # # #             response = await client.post(poll_url)
            
# # # # # #             # Parse response
# # # # # #             response_lines = response.text.strip().split('\n')
# # # # # #             response_data = {}
            
# # # # # #             for line in response_lines:
# # # # # #                 if '=' in line:
# # # # # #                     key, value = line.split('=', 1)
# # # # # #                     response_data[key.lower()] = value
            
# # # # # #             return {
# # # # # #                 "success": True,
# # # # # #                 "status": response_data.get('status', 'unknown'),
# # # # # #                 "amount": float(response_data.get('amount', '0')),
# # # # # #                 "reference": response_data.get('reference', ''),
# # # # # #                 "paynow_reference": response_data.get('paynowreference', ''),
# # # # # #                 "hash": response_data.get('hash', '')
# # # # # #             }
            
# # # # # #     except Exception as e:
# # # # # #         logger.error(f"Payment status check failed: {str(e)}")
# # # # # #         return {
# # # # # #             "success": False,
# # # # # #             "error_message": str(e)
# # # # # #         }

# # # # # # # API Endpoints
# # # # # # @router.post("/initiate", response_model=PaynowPaymentResponse)
# # # # # # async def initiate_payment(
# # # # # #     payment_request: PaynowPaymentRequest,
# # # # # #     current_user: User = Depends(get_current_active_user),
# # # # # #     db: AsyncSession = Depends(get_db)
# # # # # # ):
# # # # # #     """Initiate Paynow payment for an order"""
    
# # # # # #     # Get order
# # # # # #     result = await db.execute(
# # # # # #         select(Order).where(
# # # # # #             and_(
# # # # # #                 Order.id == payment_request.order_id,
# # # # # #                 Order.user_id == current_user.id
# # # # # #             )
# # # # # #         )
# # # # # #     )
# # # # # #     order = result.scalar_one_or_none()
    
# # # # # #     if not order:
# # # # # #         raise HTTPException(
# # # # # #             status_code=status.HTTP_404_NOT_FOUND,
# # # # # #             detail="Order not found"
# # # # # #         )
    
# # # # # #     if order.payment_status == "paid":
# # # # # #         raise HTTPException(
# # # # # #             status_code=status.HTTP_400_BAD_REQUEST,
# # # # # #             detail="Order is already paid"
# # # # # #         )
    
# # # # # #     # Create Paynow payment
# # # # # #     paynow_result = await create_paynow_payment(
# # # # # #         order=order,
# # # # # #         payment_method=payment_request.payment_method,
# # # # # #         phone_number=payment_request.phone_number,
# # # # # #         email=payment_request.email,
# # # # # #         return_url=str(payment_request.return_url) if payment_request.return_url else None
# # # # # #     )
    
# # # # # #     if not paynow_result["success"]:
# # # # # #         raise HTTPException(
# # # # # #             status_code=status.HTTP_400_BAD_REQUEST,
# # # # # #             detail=paynow_result["error_message"]
# # # # # #         )
    
# # # # # #     # Create or update payment record
# # # # # #     payment_result = await db.execute(
# # # # # #         select(Payment).where(Payment.order_id == order.id)
# # # # # #     )
# # # # # #     payment = payment_result.scalar_one_or_none()
    
# # # # # #     if not payment:
# # # # # #         payment = Payment(
# # # # # #             order_id=order.id,
# # # # # #             payment_method=payment_request.payment_method,
# # # # # #             amount=order.total_amount,
# # # # # #             currency="USD",
# # # # # #             status="pending"
# # # # # #         )
# # # # # #         db.add(payment)
    
# # # # # #     # Update payment with Paynow details
# # # # # #     payment.transaction_id = paynow_result["payment_id"]
# # # # # #     payment.gateway_response = str(paynow_result)
# # # # # #     payment.status = "pending"
    
# # # # # #     # Update order status
# # # # # #     order.payment_status = "pending"
    
# # # # # #     await db.commit()
# # # # # #     await db.refresh(payment)
    
# # # # # #     return PaynowPaymentResponse(
# # # # # #         success=True,
# # # # # #         payment_url=paynow_result.get("payment_url"),
# # # # # #         poll_url=paynow_result.get("poll_url"),
# # # # # #         payment_id=paynow_result["payment_id"],
# # # # # #         instructions=paynow_result.get("instructions")
# # # # # #     )

# # # # # # @router.get("/status/{payment_id}", response_model=PaynowStatusResponse)
# # # # # # async def check_payment_status(
# # # # # #     payment_id: str,
# # # # # #     current_user: User = Depends(get_current_active_user),
# # # # # #     db: AsyncSession = Depends(get_db)
# # # # # # ):
# # # # # #     """Check payment status"""
    
# # # # # #     # Get payment record
# # # # # #     result = await db.execute(
# # # # # #         select(Payment).join(Order).where(
# # # # # #             and_(
# # # # # #                 Payment.transaction_id == payment_id,
# # # # # #                 Order.user_id == current_user.id
# # # # # #             )
# # # # # #         )
# # # # # #     )
# # # # # #     payment = result.scalar_one_or_none()
    
# # # # # #     if not payment:
# # # # # #         raise HTTPException(
# # # # # #             status_code=status.HTTP_404_NOT_FOUND,
# # # # # #             detail="Payment not found"
# # # # # #         )
    
# # # # # #     # Extract poll URL from gateway response
# # # # # #     gateway_response = eval(payment.gateway_response) if payment.gateway_response else {}
# # # # # #     poll_url = gateway_response.get("poll_url")
    
# # # # # #     if not poll_url:
# # # # # #         raise HTTPException(
# # # # # #             status_code=status.HTTP_400_BAD_REQUEST,
# # # # # #             detail="Unable to check payment status"
# # # # # #         )
    
# # # # # #     # Check status from Paynow
# # # # # #     status_result = await check_paynow_payment_status(poll_url)
    
# # # # # #     if not status_result["success"]:
# # # # # #         raise HTTPException(
# # # # # #             status_code=status.HTTP_400_BAD_REQUEST,
# # # # # #             detail=status_result["error_message"]
# # # # # #         )
    
# # # # # #     # Update payment status if changed
# # # # # #     paynow_status = status_result["status"].lower()
    
# # # # # #     if paynow_status == "paid":
# # # # # #         payment.status = "completed"
# # # # # #         payment.processed_at = datetime.utcnow()
        
# # # # # #         # Update order
# # # # # #         order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
# # # # # #         order = order_result.scalar_one()
# # # # # #         order.payment_status = "paid"
# # # # # #         order.status = "confirmed"
        
# # # # # #     elif paynow_status in ["cancelled", "failed"]:
# # # # # #         payment.status = "failed"
        
# # # # # #         # Update order
# # # # # #         order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
# # # # # #         order = order_result.scalar_one()
# # # # # #         order.payment_status = "failed"
    
# # # # # #     await db.commit()
    
# # # # # #     return PaynowStatusResponse(
# # # # # #         success=True,
# # # # # #         status=paynow_status,
# # # # # #         payment_id=payment_id,
# # # # # #         amount=status_result["amount"],
# # # # # #         reference=status_result["reference"],
# # # # # #         paynow_reference=status_result["paynow_reference"]
# # # # # #     )

# # # # # # @router.post("/webhook")
# # # # # # async def paynow_webhook(
# # # # # #     request: Request,
# # # # # #     db: AsyncSession = Depends(get_db)
# # # # # # ):
# # # # # #     """Handle Paynow webhook notifications"""
    
# # # # # #     try:
# # # # # #         # Get form data
# # # # # #         form_data = await request.form()
# # # # # #         webhook_data = dict(form_data)
        
# # # # # #         logger.info(f"Received Paynow webhook: {webhook_data}")
        
# # # # # #         # Verify hash
# # # # # #         received_hash = webhook_data.pop('hash', '')
# # # # # #         if not verify_paynow_hash(webhook_data, received_hash, PAYNOW_CONFIG["integration_key"]):
# # # # # #             logger.error("Invalid webhook hash")
# # # # # #             raise HTTPException(
# # # # # #                 status_code=status.HTTP_400_BAD_REQUEST,
# # # # # #                 detail="Invalid hash"
# # # # # #             )
        
# # # # # #         reference = webhook_data.get('reference')
# # # # # #         paynow_status = webhook_data.get('status', '').lower()
        
# # # # # #         # Find payment by reference
# # # # # #         result = await db.execute(
# # # # # #             select(Payment).where(Payment.transaction_id == reference)
# # # # # #         )
# # # # # #         payment = result.scalar_one_or_none()
        
# # # # # #         if not payment:
# # # # # #             logger.error(f"Payment not found for reference: {reference}")
# # # # # #             return {"status": "payment not found"}
        
# # # # # #         # Update payment status
# # # # # #         if paynow_status == "paid":
# # # # # #             payment.status = "completed"
# # # # # #             payment.processed_at = datetime.utcnow()
            
# # # # # #             # Update order
# # # # # #             order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
# # # # # #             order = order_result.scalar_one()
# # # # # #             order.payment_status = "paid"
# # # # # #             order.status = "confirmed"
            
# # # # # #             logger.info(f"Payment completed for order {order.id}")
            
# # # # # #         elif paynow_status in ["cancelled", "failed"]:
# # # # # #             payment.status = "failed"
            
# # # # # #             # Update order
# # # # # #             order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
# # # # # #             order = order_result.scalar_one()
# # # # # #             order.payment_status = "failed"
            
# # # # # #             logger.info(f"Payment failed for order {order.id}")
        
# # # # # #         await db.commit()
        
# # # # # #         return {"status": "ok"}
        
# # # # # #     except Exception as e:
# # # # # #         logger.error(f"Webhook processing failed: {str(e)}")
# # # # # #         raise HTTPException(
# # # # # #             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# # # # # #             detail="Webhook processing failed"
# # # # # #         )

# # # # # # @router.get("/return")
# # # # # # async def payment_return(
# # # # # #     request: Request,
# # # # # #     db: AsyncSession = Depends(get_db)
# # # # # # ):
# # # # # #     """Handle return from Paynow payment page"""
    
# # # # # #     query_params = dict(request.query_params)
# # # # # #     reference = query_params.get('reference')
    
# # # # # #     if not reference:
# # # # # #         raise HTTPException(
# # # # # #             status_code=status.HTTP_400_BAD_REQUEST,
# # # # # #             detail="Missing payment reference"
# # # # # #         )
    
# # # # # #     # Find payment
# # # # # #     result = await db.execute(
# # # # # #         select(Payment).join(Order).where(Payment.transaction_id == reference)
# # # # # #     )
# # # # # #     payment = result.scalar_one_or_none()
    
# # # # # #     if not payment:
# # # # # #         raise HTTPException(
# # # # # #             status_code=status.HTTP_404_NOT_FOUND,
# # # # # #             detail="Payment not found"
# # # # # #         )
    
# # # # # #     # Return order details for frontend to handle
# # # # # #     return {
# # # # # #         "order_id": payment.order_id,
# # # # # #         "payment_status": payment.status,
# # # # # #         "reference": reference,
# # # # # #         "redirect_url": f"/order-confirmation/{payment.order_id}"
# # # # # #     }

# # # # # # # Express Checkout for Mobile Money
# # # # # # @router.post("/express", response_model=PaynowPaymentResponse)
# # # # # # async def express_checkout(
# # # # # #     payment_request: PaynowPaymentRequest,
# # # # # #     current_user: User = Depends(get_current_active_user),
# # # # # #     db: AsyncSession = Depends(get_db)
# # # # # # ):
# # # # # #     """Express checkout for mobile money payments (EcoCash, OneMoney, etc.)"""
    
# # # # # #     if payment_request.payment_method not in ["ecocash", "onemoney", "telecash"]:
# # # # # #         raise HTTPException(
# # # # # #             status_code=status.HTTP_400_BAD_REQUEST,
# # # # # #             detail="Express checkout only available for mobile money payments"
# # # # # #         )
    
# # # # # #     if not payment_request.phone_number:
# # # # # #         raise HTTPException(
# # # # # #             status_code=status.HTTP_400_BAD_REQUEST,
# # # # # #             detail="Phone number is required for mobile money payments"
# # # # # #         )
    
# # # # # #     # Use the same initiate_payment logic but with express handling
# # # # # #     return await initiate_payment(payment_request, current_user, db)

# # # # # # __all__ = ["router"]
