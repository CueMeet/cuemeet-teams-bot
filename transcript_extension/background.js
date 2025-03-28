chrome.runtime.onMessage.addListener(function (message, sender, sendResponse) {
  console.log(message.type);
  if (message.type == "new_meeting_started") {
      // Saving current tab id, to download transcript when this tab is closed
      chrome.tabs.query({active: true, currentWindow: true}, function (tabs) {
          const tabId = tabs[0].id;
          localStorage.setItem('meetingTabId', tabId);  // Store using localStorage
          console.log("Meeting tab id saved");
      });
  }
  if (message.type == "download") {
      // Invalidate tab id since transcript is downloaded, prevents double downloading of transcript from tab closed event listener
      localStorage.removeItem('meetingTabId');  // Remove tab ID from localStorage
      console.log("Meeting tab id cleared");
      downloadTranscript();
  }
  return true;
});


function downloadTranscript() {
  // Retrieve data from localStorage
  const userName = JSON.parse(localStorage.getItem('userName'));
  const transcript = JSON.parse(localStorage.getItem('transcript'));
  const chatMessages = JSON.parse(localStorage.getItem('chatMessages'));
  const meetingTitle = JSON.parse(localStorage.getItem('meetingTitle'));
  const meetingStartTimeStamp = JSON.parse(localStorage.getItem('meetingStartTimeStamp'));

  if (userName && transcript && chatMessages) {
      console.log("Transcript found for download");
  } else {
      console.log("No transcript found for download");
  }
}
