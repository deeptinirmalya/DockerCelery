from typing import Optional

from pydantic import BaseModel, Field

class ReceiptRequest(BaseModel):
    base64_string: str = Field(..., description="The raw base64 encoded string of the receipt image.")
    mime_type: str = Field("image/jpeg", description="The MIME type of the image (e.g., image/jpeg, image/png).")

class PaymentReceipt(BaseModel):
    platform_name: str = Field(description="The payment application used (e.g., PhonePe, Google Pay, Navi, Paytm).")
    transaction_type: str = Field(description="The transaction type(eg. DEBIT, CREDIT).")
    date: str = Field(description="The transaction date. Preferred format: YYYY-MM-DD.")
    time: str = Field(description="The transaction time. Preferred format: HH:MM:SS in 24hr format")
    amount: float = Field(description="The total transacted amount as a floating-point number.")
    from_account: Optional[str] = Field(None, description="Sender account details, bank name, or UPI ID if visible.")
    to_account_or_person_name: str = Field(description="Receiver name, merchant name, or destination UPI ID.")