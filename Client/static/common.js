// Common utilities for HPH Meeting web interface

let ws = null
const messageHandlers = new Map()
let messageId = 0
const pendingMessages = new Map()

// Validation regex
const USERNAME_REGEX = /^[a-zA-Z0-9_]+$/
const GMAIL_REGEX = /^[a-zA-Z0-9._%+]+@gmail.com$/

// WebSocket connection management
async function connectWebSocket() {
  return new Promise((resolve, reject) => {
    const wsUrl = `ws://${window.location.hostname}:${window.location.port}/ws`
    ws = new WebSocket(wsUrl)

    ws.onopen = () => resolve()

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        handleMessage(message)
      } catch (error) {
        console.error("[v0] Failed to parse message:", error, "Raw data:", event.data)
      }
    }

    ws.onclose = () => {
      setTimeout(() => {
        if (ws.readyState === WebSocket.CLOSED) {
          connectWebSocket().catch(console.error)
        }
      }, 3000)
    }

    ws.onerror = (error) => reject(error)

    setTimeout(() => {
      if (ws.readyState !== WebSocket.OPEN) {
        reject(new Error("Connection timeout"))
      }
    }, 10000)
  })
}

// Send message and wait for response
async function sendMessage(message) {
  return new Promise((resolve, reject) => {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      reject(new Error("WebSocket not connected"))
      return
    }

    const id = ++messageId
    message.id = id
    pendingMessages.set(id, { resolve, reject })

    try {
      ws.send(JSON.stringify(message))
    } catch (error) {
      pendingMessages.delete(id)
      reject(error)
      return
    }

    setTimeout(() => {
      if (pendingMessages.has(id)) {
        pendingMessages.delete(id)
        reject(new Error("Message timeout"))
      }
    }, 30000)
  })
}

// Handle incoming messages
function handleMessage(message) {
  if (message.id && pendingMessages.has(message.id)) {
    const { resolve } = pendingMessages.get(message.id)
    pendingMessages.delete(message.id)
    resolve(message)
    return
  }

  // Map các phản hồi không có id về pending promise gần nhất
  if ((
    message.type === "login_ok" ||
    message.type === "register_ok" ||
    message.type === "gateway_auth_ok" ||
    message.type === "rooms" ||
    message.type === "system"
  ) && pendingMessages.size > 0) {
    const firstKey = pendingMessages.keys().next().value
    if (firstKey !== undefined) {
      const { resolve } = pendingMessages.get(firstKey)
      pendingMessages.delete(firstKey)
      resolve(message)
      return
    }
  }

  const handler = messageHandlers.get(message.type)
  if (handler) {
    handler(message)
  } else {
    console.log("[v0] No handler for message type:", message.type)
  }
}

// Register message handler
function onMessage(type, handler) {
  messageHandlers.set(type, handler)
}

function offMessage(type) {
  messageHandlers.delete(type)
}

async function testConnection() {
  try {
    await connectWebSocket()
    return true
  } catch (error) {
    return false
  }
}

function getStoredCredentials() {
  return {
    username: sessionStorage.getItem("username"),
    email: sessionStorage.getItem("email"),
    token: sessionStorage.getItem("token"),
    aesKey: sessionStorage.getItem("aes_key"),
  }
}

function storeCredentials(username, email, token, aesKey) {
  sessionStorage.setItem("username", username)
  sessionStorage.setItem("email", email)
  if (token) sessionStorage.setItem("token", token)
  if (aesKey) sessionStorage.setItem("aes_key", aesKey)
}

function clearCredentials() {
  sessionStorage.removeItem("username")
  sessionStorage.removeItem("email")
  sessionStorage.removeItem("token")
  sessionStorage.removeItem("aes_key")
  sessionStorage.removeItem("currentRoom")
}

function validateUsername(username) {
  return USERNAME_REGEX.test(username)
}

function validateEmail(email) {
  return GMAIL_REGEX.test(email)
}

function createElement(tag, className, textContent) {
  const element = document.createElement(tag)
  if (className) element.className = className
  if (textContent) element.textContent = textContent
  return element
}

function escapeHtml(text) {
  const div = document.createElement("div")
  div.textContent = text
  return div.innerHTML
}

function formatTime(timestamp) {
  const date = new Date(timestamp)
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}

function showNotification(message, type = "info") {
  const notification = createElement("div", `notification notification-${type}`)
  notification.textContent = message

  Object.assign(notification.style, {
    position: "fixed",
    top: "20px",
    right: "20px",
    padding: "1rem 1.5rem",
    borderRadius: "5px",
    color: "white",
    fontWeight: "500",
    zIndex: "10000",
    maxWidth: "300px",
    wordWrap: "break-word",
  })

  const colors = { info: "#3498db", success: "#27ae60", warning: "#f39c12", error: "#e74c3c" }
  notification.style.backgroundColor = colors[type] || colors.info

  document.body.appendChild(notification)
  setTimeout(() => {
    if (notification.parentNode) {
      notification.parentNode.removeChild(notification)
    }
  }, 5000)
}

window.connectWebSocket = connectWebSocket
window.sendMessage = sendMessage
window.onMessage = onMessage
window.offMessage = offMessage
window.testConnection = testConnection
window.getStoredCredentials = getStoredCredentials
window.storeCredentials = storeCredentials
window.clearCredentials = clearCredentials
window.validateUsername = validateUsername
window.validateEmail = validateEmail
window.createElement = createElement
window.escapeHtml = escapeHtml
window.formatTime = formatTime
window.showNotification = showNotification
