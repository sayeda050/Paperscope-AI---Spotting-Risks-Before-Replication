import type { CapacitorConfig } from '@capacitor/cli';

// ── STEP 1: Replace this URL with your real deployed Vercel frontend URL ──────
const FRONTEND_URL = 'https://YOUR_VERCEL_APP.vercel.app';

const config: CapacitorConfig = {
  appId: 'com.paperscopeai.app',
  appName: 'PaperScope AI',
  webDir: 'www',

  server: {
    url: FRONTEND_URL,
    cleartext: false,
    androidScheme: 'https',
    // Only allow navigation to your own domains + Google OAuth.
    // Do NOT use '*' — that allows malicious redirects.
    allowNavigation: [
      '*.google.com',
      '*.googleapis.com',
      '*.onrender.com',
      '*.vercel.app',
    ],
  },

  android: {
    // Google OAuth WebView fix:
    // Google blocks OAuth in WebViews that identify as WebView.
    // This user-agent override makes Google see a standard Chrome browser.
    overrideUserAgent:
      'Mozilla/5.0 (Linux; Android 14; Pixel 8) ' +
      'AppleWebKit/537.36 (KHTML, like Gecko) ' +
      'Chrome/124.0.0.0 Mobile Safari/537.36',
    allowMixedContent: false,
    backgroundColor: '#ffffff',
  },
};

export default config;
