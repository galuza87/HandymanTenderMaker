from langchain_core.tools import tool
from backend.db import get_all_categories

@tool
def fetch_available_categories() -> str:
    """Returns a formatted string of all available contractor categories from the database. Use this to see what trades are available."""
    try:
        categories = get_all_categories()
        categories_str = ""
        for cat in categories:
            categories_str += f"- ID: {cat['id']} | **{cat['name']}**: {cat['description']}\n"
        return categories_str
    except Exception as e:
        return "- ID: 1 | General Handyman\n"
