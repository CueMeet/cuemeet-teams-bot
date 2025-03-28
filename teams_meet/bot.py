import os
import sys
import time
import json
import uuid
import logging
import requests
import platform
import subprocess
from datetime import datetime, timezone
from threading import Event
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from .utils import create_tar_archive, audio_file_path

from monitoring import init_highlight
from config import Settings

class JoinTeamsMeet:
    def __init__(self, meetlink, start_time_utc, end_time_utc, min_record_time=200, bot_name="Teams Bot", presigned_url_combined=None, presigned_url_audio=None, max_waiting_time=1800, project_settings:Settings=None, logger:logging=None):
        self.meetlink = meetlink
        self.start_time_utc = start_time_utc
        self.end_time_utc = end_time_utc
        self.min_record_time = min_record_time
        self.bot_name = bot_name
        self.browser = None
        self.recording_started = False
        self.stop_event = Event()
        self.recording_process = None
        self.presigned_url_combined = presigned_url_combined
        self.presigned_url_audio = presigned_url_audio
        self.output_file = f"out/{str(uuid.uuid4())}"
        self.event_start_time = None
        self.need_retry = False
        self.thread_start_time = None
        self.max_waiting_time = max_waiting_time
        self.session_ended = False 
        self.project_settings = project_settings
        self.logger = logger
        self.highlight = init_highlight(self.project_settings.HIGHLIGHT_PROJECT_ID, self.project_settings.ENVIRONMENT_NAME, "ms-teams-bot")

    def setup_browser(self):
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--start-maximized')
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-infobars')
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.6668.89 Safari/537.36')
        options.add_argument('--no-sandbox')
        options.add_argument("--disable-gpu")
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)

        options.add_argument("--use-fake-ui-for-media-stream")
        options.add_argument("--use-fake-device-for-media-stream")

        options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.media_stream_mic": 1,
            "profile.default_content_setting_values.media_stream_camera": 0,
            "profile.default_content_setting_values.geolocation": 0,
            "profile.default_content_setting_values.notifications": 0,
            "profile.default_content_setting_values.popups": 2,
            "profile.default_content_settings.popups": 2,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
        })
        options.add_argument("--auto-select-desktop-capture-source=Teams Meet")
        options.add_argument("user-data-dir=CueMeet")

        # Load the extensions
        options.add_argument('--load-extension=transcript_extension')

        browser_service = Service(ChromeDriverManager().install())

        try:
            self.browser = webdriver.Chrome(
                service=browser_service,
                options=options
            )
            self.browser.execute_script("""
                window.alert = function() { return; }
                window.confirm = function() { return true; }
                window.prompt = function() { return null; }
            """)
            logging.info("Browser launched successfully")
        except Exception as e:
            logging.error(f"Failed to launch the browser: {e}")
            self.end_session()

    def navigate_to_meeting(self):
        logging.info(f"Navigating to MS Teams Meet link: {self.meetlink}")
        try:
            self.browser.get(self.meetlink)
            logging.info("Successfully navigated to the MS Teams Meet link.")
        except Exception as e:
            logging.error(f"Failed to navigate to the meeting link: {e}")
            self.browser.quit()
            self.end_session()
        time.sleep(2)
        
        try:
            continue_button = WebDriverWait(self.browser, 20).until(
                EC.presence_of_element_located((By.XPATH, "//button[contains(.,'Continue on this browser')]"))
            )
            if continue_button.is_displayed() and continue_button.is_enabled():
                continue_button.click()
                logging.info("Clicked 'Continue on this browser' button")
            else:
                logging.error("'Continue on this browser' button is not clickable.")
        except TimeoutException:
            pass
        except Exception as e:
            logging.error(f"An error occurred while clicking 'Continue on this browser' button: {e}")
        
        time.sleep(4)
        
        try: 
            continue_button = WebDriverWait(self.browser, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'Continue without audio or video')]"))
            )
            continue_button.click()
            logging.info("Successfully clicked 'Continue without audio or video' button")
        except TimeoutException:
            pass
        except Exception as e:
            logging.error(f"An error occurred while clicking 'Continue without audio or video' button: {e}")
        
        try:
            # Wait for the microphone toggle to be visible and ensure it is turned off
            mic_toggle = WebDriverWait(self.browser, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "div[data-tid='toggle-mute'][title='Microphone'][aria-checked='true']"))
            )
            if mic_toggle.get_attribute("aria-checked") == "true":
                mic_toggle.click()
                logging.info("Microphone turned off")
            else:
                logging.info("Microphone is already off")
            # Wait for the camera toggle to be visible and ensure it is turned off
            camera_toggle = WebDriverWait(self.browser, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "div[data-tid='toggle-video'][title='Camera'][aria-checked='true']"))
            )
            if camera_toggle.get_attribute("aria-checked") == "true":
                camera_toggle.click()
                logging.info("Camera turned off")
            else:
                logging.info("Camera is already off")
        except TimeoutException:
            pass
        except Exception as e:
            logging.error(f"An error occurred while trying to disable mic and camera: {e}")


    def join_meeting(self):
        logging.info("Attempting to join the meeting...")
        try: 
            name_input = WebDriverWait(self.browser, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Type your name']"))
            )
            name_input.send_keys(self.bot_name)
            logging.info("Successfully entered the Bot's name")
        except TimeoutException:
            pass
        except Exception as e:
            logging.error(f"An error occurred while entering the name: {e}")
        try:
            join_button = WebDriverWait(self.browser, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'Join now')]"))
            )
            join_button.click()
            logging.info("Successfully clicked 'Join now' button")
        except TimeoutException:
            pass
        except Exception as e:
            logging.error(f"An error occurred while joining the meeting: {e}")
        time.sleep(2)


    def check_meeting_end(self):     
        try:
            return_button = WebDriverWait(self.browser, 5).until(
                EC.presence_of_element_located((By.XPATH, "//span[contains(text(), 'Enjoy your call? Join Teams today for free')]"))
            )
            if return_button:
                logging.info("Detected 'Return to home screen' button. Meeting has ended.")
                self.browser.refresh()
                self.stop_event.set()
                self.end_session()
        except TimeoutException:
            pass
        except Exception as e:
            logging.error(f"An error occurred while checking the meeting: {e}")
        try:
            removed_text = WebDriverWait(self.browser, 5).until(
                EC.presence_of_element_located((By.XPATH, "//h1[contains(text(), \"Enjoy your call? Join Teams today for free\")]"))
            )
            if removed_text:
                logging.info("Detected exit from meeting.")
                self.end_session()
        except TimeoutException:
            pass
        except Exception as e:
            logging.error(f"An error occurred while checking the meeting: {e}")


    def check_meeting_removal(self):        
        try:
            removed_text = WebDriverWait(self.browser, 5).until(
                EC.presence_of_element_located((By.XPATH, "//h1[contains(text(), \"You've been removed from this meeting\")]"))
            )
            if removed_text:
                logging.info("Detected removal from meeting.")
                self.end_session()
        except TimeoutException:
            pass
        except Exception as e:
            logging.error(f"An error occurred while checking the meeting: {e}")


    def check_waiting_room(self):
        waiting_messages = [
            "We’ve let the organiser know that you’re waiting.",
            "When the meeting starts, we’ll let the organiser know that you’re waiting."
        ]
        for message in waiting_messages:
            escaped_message = message.replace('"', '\\"') 
            try:
                join_page = WebDriverWait(self.browser, 5).until(
                    EC.presence_of_element_located((By.XPATH, f"//h2[contains(text(), \"{escaped_message}\")]"))
                )
                if join_page:
                    logging.info(f"Detected join page")
                    return False
                else:
                    return True
            except TimeoutException:
                pass
            except Exception as e:
                logging.error(f"Error while checking for join page: {e}")
        return False


    def check_admission(self):
        try:
            # Check if the leave button is visible
            leave_button = WebDriverWait(self.browser, 5).until(
                EC.presence_of_element_located((By.XPATH, '//button[starts-with(@aria-label, "Leave")]'))
            )
            if leave_button and not self.recording_started:
                logging.info("Successfully joined the meeting. Starting recording...")
                self.start_recording()
                self.recording_started = True
        except TimeoutException:
            pass
        except Exception as e:
            logging.error(f"An error occurred while checking for leave button: {e}")
        try:
            # Check if join request was denied
            denied_message = WebDriverWait(self.browser, 5).until(
                EC.presence_of_element_located((By.XPATH, "//h1[contains(text(), 'Sorry, but you were denied access to the meeting.')]"))
            )
            if denied_message:
                logging.info("Join request was denied. Ending session.")
                self.end_session()
        except TimeoutException:
            pass
        except Exception as e:
            logging.error(f"An error occurred while checking for denied message: {e}")
        try:
            # Check for any error messages
            error_message = WebDriverWait(self.browser, 5).until(
                EC.presence_of_element_located((By.XPATH, "//h2[contains(text(), \"We couldn't find a meeting matching this ID and passcode.\")]"))
            )
            if error_message:
                logging.info(f"Error message detected: {error_message.text}")
                if "denied your request to join" in error_message.text:
                    logging.info("Join request was denied. Ending session.")
                    self.end_session()
        except TimeoutException:
            pass
        except Exception as e:
            logging.error(f"An error occurred while checking for error message: {e}")


    def fill_password(self):
        time.sleep(4)
        try:
            password_input = WebDriverWait(self.browser, 5).until(
                EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Type a meeting passcode']"))
            )
            password_input.send_keys(self.meetlink.split('?p\=')[-1])
            logging.info("Successfully entered the meeting password")
        except TimeoutException:
            pass
        except Exception as e:
            logging.error(f"An error occurred while entering the password: {e}")
        try:
            submit_button = WebDriverWait(self.browser, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'Retry')]"))
            )
            submit_button.click()
            logging.info("Successfully clicked 'Retry' button")
        except TimeoutException:
            pass
        except Exception as e:
            logging.error(f"An error occurred while clicking 'Retry' button: {e}")


    def attendee_count(self):
        count = -1
        try: 
            count_text = self.browser.find_element(
                    By.XPATH, "//span[@data-tid='roster-button-tile' and @class='fui-StyledText ___vs66bj0 fwk3njj f122n59 fy9rknc flh3ekv f1gui4cr']"
                ).text.strip()
            if count_text.isdigit():
                count = int(count_text)
        except TimeoutException:
            logging.error("Attendee count not found.")
        except NoSuchElementException:
            logging.info("Member count element not found. Likely the count is 0.")
        return count

    def start_recording(self):
        logging.info("Starting meeting audio recording with FFmpeg...")
        output_audio_file = f'{self.output_file}.opus'
        
        if platform.system() == 'Darwin':
            command = [
                "ffmpeg",
                "-f", "avfoundation",
                "-i", ":0",
                "-acodec", "libopus",
                "-b:a", "128k",
                "-ac", "2",  
                "-ar", "48000",
                output_audio_file
            ]
        elif platform.system() == 'Linux':  
            command = [
                "ffmpeg",
                "-f", "pulse",
                "-i", "default",
                "-acodec", "libopus",
                "-b:a", "128k",
                "-ac", "2",  
                "-ar", "48000",
                output_audio_file
            ]
        else:
            logging.error("Unsupported operating system for recording.")
            self.end_session()
        try:
            self.event_start_time = datetime.now(timezone.utc)
            self.recording_process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.recording_started = True
            self.recording_start_time = time.perf_counter()
            logging.info(f"Recording started. Output will be saved to {output_audio_file}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Error starting FFmpeg: {e}")
            logging.error(f"FFmpeg output: {e.output}")


    def stop_recording(self):
        if self.recording_started and self.recording_process:
            logging.info("Stopping audio recording...")
            self.recording_process.terminate()
            try:
                self.recording_process.wait()
                logging.info("Recording stopped.")
            except subprocess.TimeoutExpired:
                logging.warning("Recording process did not terminate in time. Forcibly killing it.")
                self.recording_process.kill()
                logging.info("Recording process killed.")
        else:
            logging.info("No recording was started, nothing to stop.")


    def save_transcript(self):
        logging.info("started saving tanscript")
        if not self.browser:
            logging.error("Browser is not available. Cannot save transcript.")
            return

        try:
            transcript_data = self.browser.execute_script("return localStorage.getItem('transcript');")
            chat_messages_data = self.browser.execute_script("return localStorage.getItem('chatMessages');")
            meeting_title = self.browser.execute_script("return localStorage.getItem('meetingTitle');")

            transcript = json.loads(transcript_data) if transcript_data else None
            chat_messages = json.loads(chat_messages_data) if chat_messages_data else None

            transcript_json = {
                'title': meeting_title if meeting_title else None,
                'meeting_start_time': self.event_start_time.isoformat() if self.event_start_time else None,
                'meeting_end_time': datetime.now(timezone.utc).isoformat(),
                'transcript': transcript,
                'chat_messages': chat_messages,
            }

            full_path = os.path.join(os.getcwd(), f"{self.output_file}.json")
            with open(full_path, 'w', encoding='utf-8') as file:
                json.dump(transcript_json, file, ensure_ascii=False, indent=2)
            logging.info(f"Transcript saved to {self.output_file}.json")
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON format in localStorage: {e}")
        except Exception as e:
            logging.error(f"Error downloading transcript: {e}")


    def upload_files(self):
        try: 
            if self.presigned_url_combined:
                full_path = create_tar_archive(f"{self.output_file}.json", f"{self.output_file}.opus", self.output_file)
                if full_path and os.path.exists(full_path):
                    logging.info(f"Attempting to upload the Tar file from path: {full_path}")
                    try:
                        logging.info(f"Uploading {f'{self.output_file}.tar'} to pre-signed URL...")
                        with open(full_path, 'rb') as file:
                            response = requests.put(self.presigned_url_combined, data=file, headers={'Content-Type': 'application/x-tar'})
                            response.raise_for_status()
                        logging.info("Tar file uploaded successfully.")
                    except Exception as e:
                        logging.error(f"Error uploading the Tar file: {e}")
                else:
                    logging.error(f"Tar file does not exist at: {full_path}")
            else:
                logging.info("No pre-signed Tar URL provided or no Tar file to upload.")
            
            if self.presigned_url_audio:
                full_path = audio_file_path(f"{self.output_file}.opus")
                if full_path and os.path.exists(full_path):
                    logging.info(f"Attempting to upload the Audio file from path: {full_path}")
                    try:
                        logging.info(f"Uploading {f'{self.output_file}.opus'} to pre-signed URL...")
                        with open(full_path, 'rb') as file:
                            response = requests.put(self.presigned_url_audio, data=file, headers={'Content-Type': 'audio/opus'})
                            response.raise_for_status()
                        logging.info("Audio file uploaded successfully.")
                    except Exception as e:
                        logging.error(f"Error uploading the Audio file: {e}")
                else:
                    logging.error(f"Audio file does not exist at: {full_path}")
            else:
                logging.info("No pre-signed Audio URL provided or no Audio file to upload.")
        except Exception as e:
            logging.error(f"Error during file upload: {e}")


    def end_session(self):
        if self.session_ended:
            logging.info("Session has already been ended. Skipping end_session method call.")
            return
        self.session_ended = True
        logging.info("Ending the session...")
        try:
            time.sleep(10)
            if self.browser and self.recording_started:
                logging.info("Initiating transcript save...")
                try:
                    self.save_transcript()
                    logging.info("Transcript is saved.")
                except Exception as e:
                    logging.error(f"Failed to save transcript: {e}")
            time.sleep(20)
            if self.browser:
                try:
                    self.browser.quit()
                    logging.info("Browser closed.")
                except Exception as e:
                    logging.error(f"Failed to close browser: {e}")
            self.stop_event.set()
            if self.recording_started:
                self.stop_recording()
                self.upload_files()
            else:
                logging.info("No recording was started during this session.")
        except Exception as e:
            logging.error("Error during session cleanup %s", str(e), exc_info=True)
        finally:
            logging.info("Session ended successfully.")
            sys.exit(0)


    def monitor_meeting(self, initial_elapsed_time=0):        
        logging.info("Started monitoring the meeting.")
        start_time = time.perf_counter() - initial_elapsed_time

        low_member_count_end_time = None

        while not self.stop_event.is_set():
            current_time = time.perf_counter()
            elapsed_time = current_time - start_time
            # Before being admitted, check if max_waiting_time has been exceeded
            if not self.recording_started:
                if elapsed_time > self.max_waiting_time:
                    logging.info(f"Maximum waiting time ({self.max_waiting_time} seconds) exceeded. Ending session.")
                    break
            else: 
                recording_elapsed_time = current_time - self.recording_start_time
                if recording_elapsed_time > self.min_record_time:
                    logging.info(f"Minimum recording time ({self.min_record_time} seconds) reached. Ending session.")
                    break
            if self.need_retry:
                logging.info("Need to retry joining the meeting. Exiting monitoring loop.")
                break

            try:
                self.check_meeting_end()
                self.check_meeting_removal()
                self.check_admission()
                # self.check_unmute_request() # TODO: Implement this function

                if self.check_waiting_room() is False:
                    # We are in the meeting
                    members = self.attendee_count()
                    if members > 1:
                        # Other participants are present; reset the low member count timer
                        if low_member_count_end_time is not None:
                            logging.info("Member count increased. Cancelling 5-minute timer.")
                            low_member_count_end_time = None
                    else:
                        # Only the bot is in the meeting
                        if low_member_count_end_time is None:
                            low_member_count_end_time = current_time + 300  # 5 minutes
                            logging.info("Member count is 1 or less. Starting 5-minute timer.")
                        else:
                            time_left = int((low_member_count_end_time - current_time) / 60)
                            if time_left <= 0:
                                logging.info("Member count has been 1 or less for 5 minutes. Ending session.")
                                break
                            else:
                                logging.info(f"Member count still low. {time_left} minutes left before ending session.")
                else:
                    # Waiting to be admitted to the meeting
                    logging.info("Waiting to be admitted to the meeting.")
            except WebDriverException:
                logging.error("Browser has been closed. Stopping monitoring.")
                break
            except Exception as e:
                logging.error(f"Error during monitoring: {e}")
            time.sleep(2)


    def retry_join(self):
        logging.info("Retrying to join the meeting...")
        time.sleep(10)
        try:
            self.browser.refresh()
            self.navigate_to_meeting()
            self.join_meeting()
        except Exception as e:
            logging.error("Error during retry join: %s", str(e), exc_info=True)
            self.end_session()
    

    def run(self):
        try:
            logging.info("Meeting bot execution started.")
            self.setup_browser()
            self.navigate_to_meeting()
            self.fill_password()
            self.join_meeting()

            self.thread_start_time = time.perf_counter()
            total_elapsed_time = 0

            self.stop_event.clear()
            self.need_retry = False

            while True:
                self.monitor_meeting(initial_elapsed_time=total_elapsed_time)
                total_elapsed_time = time.perf_counter() - self.thread_start_time

                if self.need_retry:
                    logging.info("Retry flag is set. Proceeding to retry joining the meeting.")
                    self.need_retry = False
                    self.retry_join()
                else:
                    logging.info("Monitoring completed without retry. Exiting.")
                    break

        except Exception as e:
            logging.error("An error occurred during the meeting session. %s", str(e), exc_info=True)
        finally:
            logging.info("Finalizing the meeting session.")
            self.end_session()
        logging.info("Meeting bot has successfully completed its run.")