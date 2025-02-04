# telegram_bot.py

import os
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler
import logging
from datetime import datetime
from dotenv import load_dotenv
import json  # <-- Import json
import re  # For cleaning the force name
from pymongo import MongoClient  # For MongoDB connection


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
    # Collect user input and metadata
    raw_text = context.user_data['raw_text']
    grades_data = context.user_data['grades_data']
    date_str = datetime.now().strftime('%d/%m/%Y')

    manager_name = context.user_data.get('manager_name', "Training Manager")
    force_name = context.user_data.get('force_name', "Training Force")
    location = context.user_data.get('location', "Training Location")
    youtube_link = context.user_data.get('youtube_link', None)
    poll_link = context.user_data.get('poll_link', None)

    try:
        # Format the force name for a valid primary key
        cleaned_force_name = re.sub(r'\s+', '_', force_name.strip())
        primary_key = f"{date_str}_{cleaned_force_name}"

        # Enhance text using GPT and parse into sections
        enhanced_text = improve_text(raw_text, date_str, manager_name, force_name, location)
        sections = parse_to_sections(enhanced_text)

        # Prepare JSON data
        json_data = {
            "primary_key": primary_key,
            "date": date_str,
            "force_name": force_name,
            "gpt_output": {
                "scenario_1": sections.get("Exercise 1", ""),
                "scenario_2": sections.get("Exercise 2", "")
            },
            "grades": grades_data,
            "poll_link": poll_link or "NONE",
            "youtube_link": youtube_link or "NONE"
        }

        # Upload JSON to MongoDB
        mongo_uri = os.getenv("MONGO_URI")  # Ensure this exists in your .env file
        client = MongoClient(mongo_uri)
        db = client["Training_Reports"]  # Matches your MongoDB database name
        collection = db["Training_Sessions"]  # Matches your collection name
        result = collection.insert_one(json_data)

        # Confirm upload success
        if result.inserted_id:
            await update.message.reply_text(f"JSON successfully uploaded with ID: {result.inserted_id}")
        else:
            await update.message.reply_text("Failed to upload JSON to MongoDB.")

        # Save Word report locally
        doc_output_path = "../resources/combat_report.docx"
        generate_word_document(
            sections,
            output_path=doc_output_path,
            date=date_str,
            signature=manager_name,
            title="Training Report",
            grades_data=grades_data,
            youtube_link=youtube_link,
            poll_link=poll_link
        )

        # Send Word report to user
        with open(doc_output_path, 'rb') as doc:
            await update.message.reply_document(doc)

        # Send JSON file to user
        json_file_path = f"../resources/{primary_key}.json"  # Unique file per session
        with open(json_file_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)

        with open(json_file_path, 'rb') as json_file:
            await update.message.reply_document(document=json_file)

        await update.message.reply_text('The report was generated and sent successfully. Thank you!')
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        await update.message.reply_text('An error occurred while generating the report. Please try again later.')

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
