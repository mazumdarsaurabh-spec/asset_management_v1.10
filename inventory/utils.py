# inventory_management/inventory/utils.py
import uuid

def generate_uid_no():
    """
    Generates a unique, short ID for InventoryItem.uid_no.
    Example: INV-UUID_PART (e.g., INV-A1B2C3D4)
    """
    return f"INV-{str(uuid.uuid4()).split('-')[0].upper()}"