from langchain_core.tools import tool
from backend.v1.db.database import get_all_categories_with_subs

@tool
def fetch_available_categories() -> str:
    """Returns a formatted string of all available contractor categories from the database. Use this to see what trades are available."""
    try:
        categories = get_all_categories_with_subs()
        categories_str = ""
        for cat in categories:
            subs = ", ".join([f"{sub['name']}" for sub in cat["subcategories"]])
            categories_str += f"- ID: {cat['id']} | **{cat['name']}**: {subs}\n"
        return categories_str
    except Exception as e:
        return "- ID: 1 | General Handyman\n"
