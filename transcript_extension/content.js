let transcript = [];
let chatMessages = [];

function waitForElementById(id, callback) {
    const observer = new MutationObserver((mutationsList, observer) => {
        const element = document.getElementById(id);
        if (element) {
            callback(element);
            observer.disconnect();
        }
    });

    observer.observe(document.body, { childList: true, subtree: true });

    const element = document.getElementById(id);
    if (element) {
        callback(element);
        observer.disconnect();
    }
}

function pushUniqueChatBlock(chatBlock) {
  const isExisting = chatMessages.some(item =>
    item.personName === chatBlock.personName &&
    item.timeStamp === chatBlock.timeStamp &&
    chatBlock.chatMessageText.includes(item.chatMessageText)
  );
  
  if (!isExisting) {
    chatMessages.push(chatBlock);
  }
}

function overWriteChromeStorage(keys, sendDownloadMessage) {
    if (keys.includes("transcript")) {
      localStorage.setItem('transcript', JSON.stringify(transcript));
    }
    if (keys.includes("chatMessages")) {
      localStorage.setItem('chatMessages', JSON.stringify(chatMessages));
    }
  
    if (sendDownloadMessage && transcript.length > 0) {
      chrome.runtime.sendMessage({ type: "download" }, function(response) {
        console.log(response);
      });
    }
}

function waitForLanguageSpeechMenuItem() {
    return new Promise((resolve) => {
        const observer = new MutationObserver((mutationsList, observer) => {
            const languageMenuItem = document.getElementById("LanguageSpeechMenuControl-id");
            if (languageMenuItem) {
                observer.disconnect();
                languageMenuItem.click();
                console.log("Language and speech menu item clicked");
                resolve(languageMenuItem);
            }
        });

        observer.observe(document.body, { childList: true, subtree: true });

        const languageMenuItem = document.getElementById("LanguageSpeechMenuControl-id");
        if (languageMenuItem) {
            observer.disconnect();
            languageMenuItem.click();
            console.log("Language and speech menu item clicked");
            resolve(languageMenuItem);
        }
    });
}

function waitForLiveCaptionsButton() {
    return new Promise((resolve) => {
        const observer = new MutationObserver((mutationsList, observer) => {
            const captionsButton = document.getElementById("closed-captions-button");
            if (captionsButton) {
                observer.disconnect();
                captionsButton.click();
                console.log("Show live captions button clicked");
                resolve(captionsButton);
            }
        });

        observer.observe(document.body, { childList: true, subtree: true });

        const captionsButton = document.getElementById("closed-captions-button");
        if (captionsButton) {
            observer.disconnect();
            captionsButton.click();
            console.log("Show live captions button clicked");
            resolve(captionsButton);
        }
    });
}

function waitForChatButton() {
    return new Promise((resolve) => {
      const observer = new MutationObserver((mutationsList, observer) => {
          const chatButton = document.getElementById("chat-button");
          if (chatButton) {
              observer.disconnect();
              chatButton.click();
              console.log("Show chat button clicked");
              resolve(chatButton);
          }
      });

      observer.observe(document.body, { childList: true, subtree: true });

      const chatButton = document.getElementById("chat-button");
      if (chatButton) {
          observer.disconnect();
          chatButton.click();
          console.log("Show chat button clicked");
          resolve(chatButton);
      }
    });
}

function monitorMessages() {
  console.log("Starting to monitor chat messages...");
  
  const chatObserver = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
          if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
              mutation.addedNodes.forEach(node => {
                  if (node.nodeType === Node.ELEMENT_NODE) {
                      if (node.classList && node.classList.contains('fui-ChatMessage__body')) {
                          processMessage(node);
                      } else {
                          const messageElements = node.querySelectorAll('.fui-ChatMessage__body');
                          messageElements.forEach(messageElement => {
                              processMessage(messageElement);
                          });
                      }
                  }
              });
          }
      }
  });
  
  function processMessage(element) {
      const usernameElement = element.closest('.fui-ChatMessage').querySelector('.fui-ChatMessage__author span[data-tid="message-author-name"]');
      const messageTextElement = element.querySelector('[dir="auto"]');
      
      if (usernameElement && messageTextElement) {
          const username = usernameElement.textContent.trim();
          const messageText = messageTextElement.textContent.trim();
          const timeStamp = new Date().toISOString();

          const chatMessageBlock = {
            personName: username,
            timeStamp: timeStamp,
            chatMessageText: messageText
          };
          
          if (messageText.length > 0) {
            pushUniqueChatBlock(chatMessageBlock);
            overWriteChromeStorage(["chatMessages"], false);
          }
      }
  }
  
  chatObserver.observe(document.body, { 
      childList: true, 
      subtree: true
  });
  
  console.log("Chat message monitoring activated - logging all new messages");
}

function monitorCaptions() {
  
  const captionsObserver = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      if (mutation.type === 'childList') {
        mutation.addedNodes.forEach(node => {
          if (node.nodeType === Node.ELEMENT_NODE) {
            const captionElements = node.querySelectorAll('.ui-chat__item__message');
            captionElements.forEach(captionElement => {
              const usernameElement = captionElement.querySelector('.ui-chat__message__author');
              const textElement = captionElement.querySelector('[data-tid="closed-caption-text"]');
              
              if (usernameElement && textElement) {
                const username = usernameElement.textContent.trim();
                const text = textElement.textContent.trim();
                const timestamp = new Date().toISOString();
                
                if (text.length > 0) {
                  transcript.push({
                    "personName": username,
                    "timeStamp": timestamp,
                    "personTranscript": text
                  });
                  
                  console.log(`Caption recorded: ${username}: "${text}"`);
                  overWriteChromeStorage(["transcript"], false);
                }
              }
            });
          }
        });
      }
    }
  });
  
  captionsObserver.observe(document.body, { 
    childList: true, 
    subtree: true
  });
  
  window.addEventListener('beforeunload', () => {
    console.log("Page unloading - saving final transcript");
    overWriteChromeStorage(["transcript"], true);
  });
}

waitForElementById("callingButtons-showMoreBtn", async (moreButton) => {
    console.log("More button found, clicking it...");
    moreButton.click();
    
    await waitForLanguageSpeechMenuItem();
    await waitForLiveCaptionsButton();
    await waitForChatButton();
    
    console.log("All buttons clicked, now monitoring captions and messages...");
    
    monitorCaptions();
    monitorMessages();
});