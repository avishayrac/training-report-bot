# telegram_bot.py

import os
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler
import logging
from datetime import datetime
from dotenv import load_dotenv
import json  # <-- Import json

# Import your existing modules
from app.controllers.gpt_integration import improve_text, parse_to_sections
from app.controllers.grades import collect_grades_telegram, COLLECT_GRADES, COLLECT_YOUTUBE_LINK
from app.controllers.document_generator import generate_word_document

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Define conversation states
(
    INPUT_TEXT,
    COLLECT_MANAGER_NAME,
    COLLECT_FORCE_NAME,
    COLLECT_LOCATION,
    COLLECT_GRADES,
    COLLECT_YOUTUBE_LINK,
    COLLECT_POLL_LINK,
    GENERATE_REPORT
) = range(8)


async def start(update, context):
    await update.message.reply_text(
        "ברוך הבא למייצר דוחות אימון של חברת DCA.\n אנא הכניסו טקסט בתבנית הבאה:\n"
        "תקציר התרגיל הראשון בנקודות\n"
        "מה היה טוב בתרגיל הראשון\n"
        "איפה הכוח צריך להשתפר\n"
        "תקציר התרגיל השני בנקודות\n"
        "מה היה טוב בתרגיל הראשון\n"
        "איפה הכוח צריך להשתפר\n"
    )
    return INPUT_TEXT


async def input_text(update, context):
    context.user_data['raw_text'] = update.message.text
    await update.message.reply_text('אנא הכנס שם מנהל תרגיל:')
    return COLLECT_MANAGER_NAME


async def collect_manager_name(update, context):
    context.user_data['manager_name'] = update.message.text
    await update.message.reply_text('אנא הכנס שם הכוח המתאמן:')
    return COLLECT_FORCE_NAME


async def collect_force_name(update, context):
    context.user_data['force_name'] = update.message.text
    await update.message.reply_text('אנא הכנס את מיקום האימון:')
    return COLLECT_LOCATION


async def collect_location(update, context):
    context.user_data['location'] = update.message.text
    await update.message.reply_text('אנא שלח "המשך" כדי לעבור לציונים')
    return COLLECT_GRADES


async def collect_youtube_link(update, context):
    youtube_link = update.message.text.strip()
    if youtube_link.lower() != 'לא':
        context.user_data['youtube_link'] = youtube_link
    else:
        context.user_data['youtube_link'] = None
    await update.message.reply_text('אנא הכנס קישור לסקרים (או הקלד "לא" אם אין):')
    return COLLECT_POLL_LINK


async def collect_poll_link(update, context):
    poll_link = update.message.text.strip()
    if poll_link.lower() != 'לא':
        context.user_data['poll_link'] = poll_link
    else:
        context.user_data['poll_link'] = None

    await update.message.reply_text('מייצר את הדוח, אנא המתן...')

    return await generate_report(update, context)


async def generate_report(update, context):
    raw_text = context.user_data['raw_text']
    grades_data = context.user_data['grades_data']
    # Format the date as YYYY-MM-DD as requested
    date_str = datetime.now().strftime('%Y-%m-%d')

    manager_name = context.user_data.get('manager_name', "מנהל התרגיל")
    force_name = context.user_data.get('force_name', "הכוח המתאמן")
    location = context.user_data.get('location', "מיקום האימון")
    youtube_link = context.user_data.get('youtube_link')
    poll_link = context.user_data.get('poll_link')

    try:
        # Enhance text using GPT
        enhanced_text = improve_text(raw_text, date_str, manager_name, force_name, location)

        # Parse the text into sections
        sections = parse_to_sections(enhanced_text)

        # --------------------------------------------------------------------
        # JSON Generation Code (NEW)
        # We now have all the data needed to create the JSON file.
        json_data = {
            "force_name": force_name,
            "manage_name": manager_name,  # The user asked for "manage_name" key.
            "date": date_str,
            "gpt_output": enhanced_text,  # Using the entire enhanced text as GPT output.
            "grades": grades_data,        # This includes all collected grades.
            "youtube_link": youtube_link if youtube_link else "",
            "polls": poll_link if poll_link else ""
        }

        # Save the JSON to a file
        json_file_path = "../resources/data.json"
        with open(json_file_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)

        # (Optional) Send the JSON file to the user
        with open(json_file_path, 'rb') as f:
            await update.message.reply_document(document=f, filename="data.json")
        # --------------------------------------------------------------------


        # Generate the document
        doc_output_path = "../resources/combat_report.docx"
        generate_word_document(
            sections,
            output_path=doc_output_path,
            date=date_str,
            signature=manager_name,
            title="אימון בסימולטור DCA",
            grades_data=grades_data,
            youtube_link=youtube_link,
            poll_link=poll_link
        )

        # Send the document to the user
        with open(doc_output_path, 'rb') as doc:
            await update.message.reply_document(doc)

        await update.message.reply_text('הדוח נוצר ונשלח אליכם.\n תודה שהשתמשתם בשירות שלנו!\n'
                                        'נוצר על ידי Omri Rachmani')
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        await update.message.reply_text('אירעה שגיאה ביצירת הדוח. אנא נסו שוב מאוחר יותר.')

    return ConversationHandler.END


async def cancel(update, context):
    await update.message.reply_text('הפעולה בוטלה.')
    return ConversationHandler.END


def main():
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables.")
        return

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            INPUT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_text)],
            COLLECT_MANAGER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_manager_name)],
            COLLECT_FORCE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_force_name)],
            COLLECT_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_location)],
            COLLECT_GRADES: [MessageHandler(filters.ALL & ~filters.COMMAND, collect_grades_telegram)],
            COLLECT_YOUTUBE_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_youtube_link)],
            COLLECT_POLL_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_poll_link)],
            GENERATE_REPORT: [MessageHandler(filters.ALL & ~filters.COMMAND, generate_report)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)

    application.run_polling()


if __name__ == '__main__':
    main()
