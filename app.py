from teams_meet.bot import JoinTeamsMeet
from utils import clean_meeting_link, convert_timestamp_to_utc
import argparse
import sys
import logging

from config import get_settings
from logger import LogConfig


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description="Join a Teams Meeting to record audio.")
        parser.add_argument("meetlink", help="The Teams Meet link to join")
        parser.add_argument("--start-time", type=int, default=None, help="Meeting start time (JavaScript timestamp in milliseconds)")
        parser.add_argument("--end-time", type=int, default=None, help="Meeting end time (JavaScript timestamp in milliseconds)")
        parser.add_argument("--min-record-time", type=int, default=7200, help="Minimum recording time in seconds (Default: 2 hours)")
        parser.add_argument("--bot-name", default="CueMeet Assistant", help="Name of the bot in the meeting (Default: 'CueMeet Assistant')")
        parser.add_argument("--presigned-url-combined", default=None, help="Tar file presigned URL to upload the recording file and transcription file")
        parser.add_argument("--presigned-url-audio", default=None, help="Audio file presigned URL to upload the recording file")
        parser.add_argument("--max-waiting-time", type=int, default=1800, help="Maximum waiting time in seconds (Default: 30 minutes)")

        args = parser.parse_args()

        meet_bot = JoinTeamsMeet(
            meetlink=clean_meeting_link(args.meetlink),
            start_time_utc=convert_timestamp_to_utc(args.start_time) if args.start_time else None,
            end_time_utc = convert_timestamp_to_utc(args.end_time) if args.end_time else None,
            min_record_time=args.min_record_time,
            bot_name=args.bot_name,
            presigned_url_combined=args.presigned_url_combined,
            presigned_url_audio=args.presigned_url_audio,
            max_waiting_time=args.max_waiting_time,
            project_settings=get_settings(),
            logger=LogConfig().get_logger("Teams Meet Bot")
        )
        meet_bot.run()
    finally:
        logging.info("Bot has finished running. Exiting the application.")
        sys.exit(0)