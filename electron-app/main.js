const { app, BrowserWindow, Menu, dialog, nativeImage, shell } = require("electron");
const fs = require("fs");
const https = require("https");
const path = require("path");
const { pathToFileURL } = require("url");

const APP_URL = "https://atms.76.13.138.71.sslip.io/";
const ALLOWED_ORIGIN = new URL(APP_URL).origin;
const DJANGO_ROOT = path.resolve(__dirname, "..");

let mainWindow = null;
let loadingWindow = null;

function resolveBrandLogoPath() {
  const packagedBrandLogo = path.join(__dirname, "build", "logo.png");
  if (fs.existsSync(packagedBrandLogo)) {
    return packagedBrandLogo;
  }

  const settingsDir = path.join(DJANGO_ROOT, "media", "settings");
  if (fs.existsSync(settingsDir)) {
    const preferredLogo = fs
      .readdirSync(settingsDir)
      .filter((file) => /\.(png|jpg|jpeg|webp|bmp)$/i.test(file))
      .map((file) => path.join(settingsDir, file))
      .sort((left, right) => fs.statSync(right).mtimeMs - fs.statSync(left).mtimeMs)[0];

    if (preferredLogo && fs.existsSync(preferredLogo)) {
      return preferredLogo;
    }
  }

  return path.join(DJANGO_ROOT, "static", "img", "Afrilott.png");
}

const APP_ICON_PATH = resolveBrandLogoPath();
const APP_ICON_URL = pathToFileURL(APP_ICON_PATH).href;

function createAppIcon() {
  try {
    const logoBase64 = fs.readFileSync(APP_ICON_PATH).toString("base64");
    const svg = `
      <svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
        <defs>
          <filter id="logoToWhite" color-interpolation-filters="sRGB">
            <feColorMatrix
              type="matrix"
              values="0 0 0 0 1
                      0 0 0 0 1
                      0 0 0 0 1
                      0 0 0 1 0"
            />
          </filter>
        </defs>
        <rect width="512" height="512" rx="124" fill="#0F5B2A" />
        <image
          href="data:image/png;base64,${logoBase64}"
          x="86"
          y="86"
          width="340"
          height="340"
          preserveAspectRatio="xMidYMid meet"
          filter="url(#logoToWhite)"
        />
      </svg>
    `;
    return nativeImage.createFromDataURL(`data:image/svg+xml;base64,${Buffer.from(svg).toString("base64")}`);
  } catch (_error) {
    return nativeImage.createFromPath(APP_ICON_PATH);
  }
}

function buildLoadingHtml(message) {
  return `
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8" />
      <title>ATMS Loading</title>
      <style>
        body {
          margin: 0;
          font-family: "Segoe UI", Arial, sans-serif;
          background:
            radial-gradient(circle at top left, rgba(255, 255, 255, 0.10), transparent 24%),
            radial-gradient(circle at bottom right, rgba(255, 255, 255, 0.08), transparent 26%),
            linear-gradient(135deg, #0f5b2a 0%, #0c6b33 52%, #0a4c23 100%);
          color: #ffffff;
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 100vh;
          overflow: hidden;
        }
        body::before,
        body::after {
          content: "";
          position: absolute;
          border-radius: 999px;
          filter: blur(10px);
          opacity: 0.45;
        }
        body::before {
          width: 280px;
          height: 280px;
          top: -70px;
          right: -60px;
          background: rgba(255, 255, 255, 0.10);
        }
        body::after {
          width: 220px;
          height: 220px;
          bottom: -50px;
          left: -40px;
          background: rgba(255, 255, 255, 0.08);
        }
        .card {
          position: relative;
          z-index: 1;
          width: min(460px, 90vw);
          background: linear-gradient(180deg, rgba(255, 255, 255, 0.12), rgba(255, 255, 255, 0.07));
          border: 1px solid rgba(255, 255, 255, 0.16);
          border-radius: 28px;
          padding: 34px;
          box-shadow: 0 28px 65px rgba(6, 40, 19, 0.34);
          backdrop-filter: blur(16px);
        }
        .brand {
          display: flex;
          align-items: center;
          gap: 14px;
          margin-bottom: 14px;
        }
        .brand-mark {
          width: 58px;
          height: 58px;
          border-radius: 18px;
          background: #0f5b2a;
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 10px 25px rgba(6, 40, 19, 0.18);
          overflow: hidden;
        }
        .brand-mark img {
          width: 78%;
          height: 78%;
          object-fit: contain;
          filter: brightness(0) invert(1);
        }
        .eyebrow {
          font-size: 12px;
          font-weight: 700;
          letter-spacing: 0.18em;
          text-transform: uppercase;
          color: #bbf7d0;
        }
        h1 {
          margin: 10px 0 10px;
          font-size: 28px;
          line-height: 1.2;
        }
        p {
          margin: 0;
          color: rgba(255, 255, 255, 0.85);
          line-height: 1.6;
        }
        .status {
          margin-top: 18px;
          display: inline-flex;
          align-items: center;
          gap: 8px;
          border-radius: 999px;
          background: rgba(255, 255, 255, 0.10);
          border: 1px solid rgba(255, 255, 255, 0.14);
          padding: 9px 14px;
          font-size: 12px;
          letter-spacing: 0.06em;
          text-transform: uppercase;
          color: rgba(255, 255, 255, 0.88);
        }
        .dots {
          display: inline-flex;
          gap: 8px;
          margin-top: 22px;
        }
        .dots span {
          width: 10px;
          height: 10px;
          border-radius: 999px;
          background: #ffffff;
          animation: pulse 1.1s infinite ease-in-out;
        }
        .dots span:nth-child(2) { animation-delay: 0.15s; }
        .dots span:nth-child(3) { animation-delay: 0.3s; }
        @keyframes pulse {
          0%, 100% { opacity: 0.35; transform: translateY(0); }
          50% { opacity: 1; transform: translateY(-3px); }
        }
      </style>
    </head>
    <body>
      <div class="card">
        <div class="brand">
          <div class="brand-mark">
            <img src="${APP_ICON_URL}" alt="Afrilott logo" />
          </div>
          <div>
            <div class="eyebrow">Afrilott Transport</div>
            <div style="font-size: 15px; color: rgba(255,255,255,0.9); font-weight: 600;">Desktop Workspace</div>
          </div>
        </div>
        <h1>Starting desktop app</h1>
        <p>${message}</p>
        <div class="status">Connecting to live system</div>
        <div class="dots"><span></span><span></span><span></span></div>
      </div>
    </body>
    </html>
  `;
}

function setLoadingScreen(message) {
  if (!loadingWindow || loadingWindow.isDestroyed()) {
    return;
  }
  loadingWindow.loadURL(`data:text/html;charset=UTF-8,${encodeURIComponent(buildLoadingHtml(message))}`);
}


function buildAppMenu() {
  const template = [
    ...(process.platform === "darwin"
      ? [{
          label: app.name,
          submenu: [
            { role: "quit" }
          ]
        }]
      : []),
    {
      label: "File",
      submenu: [
        { role: process.platform === "darwin" ? "close" : "quit" }
      ]
    },
    {
      label: "View",
      submenu: [
        { role: "reload" },
        { role: "forceReload" },
        { type: "separator" },
        { role: "toggleDevTools" },
        { type: "separator" },
        { role: "resetZoom" },
        { role: "zoomIn" },
        { role: "zoomOut" },
        { type: "separator" },
        { role: "togglefullscreen" }
      ]
    }
  ];

  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

function createLoadingWindow() {
  const appIcon = createAppIcon();
  loadingWindow = new BrowserWindow({
    width: 400,
    height: 300,
    resizable: false,
    maximizable: false,
    minimizable: false,
    fullscreenable: false,
    autoHideMenuBar: true,
    title: "Afrilott ATMS",
    icon: appIcon,
    backgroundColor: "#0f5b2a",
    show: false,
    frame: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      partition: "persist:afrilott-atms"
    }
  });

  loadingWindow.once("ready-to-show", () => {
    loadingWindow.show();
  });

  loadingWindow.on("closed", () => {
    loadingWindow = null;
  });

  setLoadingScreen("Starting system... Please wait");
}

function createMainWindow() {
  const appIcon = createAppIcon();
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1100,
    minHeight: 760,
    autoHideMenuBar: true,
    title: "Afrilott ATMS",
    icon: appIcon,
    backgroundColor: "#0f5b2a",
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      partition: "persist:afrilott-atms"
    }
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (isAllowedUrl(url)) {
      return { action: "allow" };
    }

    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.webContents.on("will-navigate", (event, url) => {
    if (!isAllowedUrl(url)) {
      event.preventDefault();
    }
  });

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

function isAllowedUrl(rawUrl) {
  try {
    return new URL(rawUrl).origin === ALLOWED_ORIGIN;
  } catch (_error) {
    return false;
  }
}

function tryRequest(url) {
  return new Promise((resolve) => {
    const request = https.get(url, (response) => {
      response.resume();
      resolve(response.statusCode && response.statusCode >= 200 && response.statusCode < 400);
    });

    request.on("error", () => resolve(false));
    request.setTimeout(1500, () => {
      request.destroy();
      resolve(false);
    });
  });
}

async function waitForServer(url, timeoutMs = 30000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    if (await tryRequest(url)) {
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  return false;
}

async function bootApplication() {
  createLoadingWindow();

  const serverReady = await waitForServer(APP_URL, 30000);
  if (!serverReady) {
    setLoadingScreen("No internet connection. Please connect and try again.");
    dialog.showErrorBox(
      "Connection unavailable",
      "No internet connection. Please connect and try again."
    );
    return;
  }

  createMainWindow();

  if (mainWindow && !mainWindow.isDestroyed()) {
    await mainWindow.loadURL(APP_URL);
    mainWindow.setTitle("Afrilott ATMS");
  }

  if (loadingWindow && !loadingWindow.isDestroyed()) {
    loadingWindow.close();
  }
}

app.whenReady().then(() => {
  if (process.platform === "win32") {
    app.setAppUserModelId("com.atms.desktop");
  }
  const appIcon = createAppIcon();
  buildAppMenu();
  if (process.platform === "darwin" && app.dock) {
    app.dock.setIcon(appIcon);
  }
  return bootApplication();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", async () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    await bootApplication();
  }
});
