from typing import Dict, Any, List

class AddressService:
    @staticmethod
    def validate_address(address_str: str) -> Dict[str, Any]:
        """
        USPS / Loqate Address Validation simulation.
        Checks if address is valid and returns normalized components.
        """
        if not address_str or address_str.strip() == "" or "tbd" in address_str.lower():
            return {"valid": False, "reason": "Missing address data", "normalized": None}
        
        # Simulating address verification
        # Let's say if it doesn't contain a number, it's invalid
        parts = address_str.split(",")
        if len(parts) < 2:
            return {"valid": False, "reason": "Malformed address format", "normalized": None}
            
        return {
            "valid": True,
            "reason": "Verified by Loqate",
            "normalized": {
                "street": parts[0].strip(),
                "city": parts[1].strip() if len(parts) > 1 else "",
                "state": parts[2].strip() if len(parts) > 2 else "",
                "zip": parts[3].strip() if len(parts) > 3 else "94103"
            }
        }

class InventoryService:
    @staticmethod
    def check_stock(category: str, amount: float) -> Dict[str, Any]:
        """
        NetSuite ERP Inventory check simulation.
        Determines if stock is allocated.
        """
        # If order amount is huge or category is ?, stock allocation might require PO check
        if category == "?" or not category:
            return {"allocated": False, "stock_level": 0, "status": "backorder"}
        
        # Simulating stock allocation based on category
        return {
            "allocated": True,
            "stock_level": 150,
            "status": "in_stock"
        }

class CarrierService:
    @staticmethod
    def rate_shop(weight_lbs: float = 1.0) -> Dict[str, Any]:
        """
        Shippo / EasyPost Carrier Rate Shopping simulation.
        Selects the cheapest carrier rate.
        """
        rates = [
            {"carrier": "USPS", "service": "Ground Advantage", "rate": 5.50},
            {"carrier": "UPS", "service": "Ground", "rate": 8.90},
            {"carrier": "FedEx", "service": "Home Delivery", "rate": 11.20}
        ]
        # Cheapest is USPS
        cheapest = min(rates, key=lambda x: x["rate"])
        return {
            "rates": rates,
            "cheapest": cheapest
        }

class FraudService:
    @staticmethod
    def check_fraud(customer: str, amount: float, notes: str) -> Dict[str, Any]:
        """
        Signifyd + ERP Fraud review simulation.
        """
        score = 98
        decision = "approved"
        
        notes_lower = notes.lower() if notes else ""
        if "review" in notes_lower or "unclear" in notes_lower:
            score = 65
            decision = "needs_manual_review"
        elif amount > 30000:
            score = 75
            decision = "needs_manual_review"
            
        return {
            "score": score,
            "decision": decision
        }
