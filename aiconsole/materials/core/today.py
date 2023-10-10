from datetime import datetime


def content(context):
    # Get current date
    current_date = datetime.now()

    # Format as string
    current_date_string = current_date.strftime("%A, %B %d, %Y")

    return f"""
# Today

Today is {current_date_string}
""".strip()


material = {
    "usage": "When you need to know what is the Today's date",
    "content": content,
}