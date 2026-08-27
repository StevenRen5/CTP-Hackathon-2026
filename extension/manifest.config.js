import { defineManifest } from '@crxjs/vite-plugin'

// The manifest is the extension's entry point. CRXJS wires the referenced
// source files (background, side panel html) into the Vite build.
export default defineManifest({
  manifest_version: 3,
  name: 'Building Report Card',
  version: '0.1.0',
  description: 'Honest NYC building intel on any Zillow / StreetEasy listing.',

  // Clicking the toolbar icon opens the side panel (behavior set in background.js).
  action: { default_title: 'Open Building Report Card' },

  background: { service_worker: 'src/background.js', type: 'module' },

  side_panel: { default_path: 'src/panel/index.html' },

  permissions: ['sidePanel', 'activeTab', 'scripting', 'tabs'],

  host_permissions: [
    'https://*.zillow.com/*',
    'https://*.streeteasy.com/*',
    'http://localhost/*',
  ],
})
