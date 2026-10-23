import { Page, Locator, expect } from '@playwright/test';

/**
 * Page Object for the Scribe tab in the Ambient Clinical AI Scribe app.
 * Encapsulates all interactions with the recording UI, transcript panel, and case sheet form.
 */
export class ScribePage {
  readonly page: Page;
  
  // Header elements
  readonly startRecordingButton: Locator;
  readonly stopRecordingButton: Locator;
  readonly connectionStatus: Locator;
  readonly captureStatus: Locator;
  readonly timerDisplay: Locator;
  readonly tabScribe: Locator;
  readonly tabPatients: Locator;
  
  // Transcript panel
  readonly transcriptPanel: Locator;
  readonly transcriptMessages: Locator;
  readonly voiceIndicator: Locator;
  readonly voiceLevelBars: Locator;
  
  // Case sheet form
  readonly caseSheetForm: Locator;
  readonly savePatientButton: Locator;
  readonly fieldTiles: Locator;
  readonly filledCountBadge: Locator;
  readonly saveStatus: Locator;
  
  // Alerts
  readonly alertBanner: Locator;
  readonly micErrorBanner: Locator;

  constructor(page: Page) {
    this.page = page;
    
    // Header - the main recording button
    this.startRecordingButton = page.locator('button:has-text("Start Recording")');
    this.stopRecordingButton = page.locator('button:has-text("Stop")');
    this.connectionStatus = page.locator('span:has-text("LIVE"), span:has-text("OFFLINE")').first();
    this.captureStatus = page.locator('text=Capture agent');
    this.timerDisplay = page.locator('text=/^⏱ \\d{2}:\\d{2}$/');
    this.tabScribe = page.locator('button:has-text("Scribe")');
    this.tabPatients = page.locator('button:has-text("Patients")');
    
    // Transcript panel
    this.transcriptPanel = page.locator('h2:has-text("Live Transcript")').locator('..').locator('..');
    this.transcriptMessages = page.locator('.animate-fade-up');
    this.voiceIndicator = page.locator('text=Hearing…');
    this.voiceLevelBars = page.locator('[class*="bg-brand-400"][style*="height"]');
    
    // Case sheet form
    this.caseSheetForm = page.locator('h2:has-text("Maternity Services Case Sheet")').locator('..').locator('..');
    this.savePatientButton = page.locator('button:has-text("Save Patient")');
    this.fieldTiles = page.locator('[class*="rounded-xl border p-3"]').filter({ hasText: /Beneficiary|Registration|Husband|RCH|Health|Block|District|IPD|BPL|Contact|ANC|Aadhaar|ASHA/ });
    this.filledCountBadge = page.locator('text=/\\d+ filled/');
    this.saveStatus = page.locator('text=/Saved|Saving|fields filled/');
    
    // Alerts
    this.alertBanner = page.locator('[class*="AlertBanner"]');
    this.micErrorBanner = page.locator('text=🎙');
  }

  /**
   * Navigate to the scribe page and wait for backend connection
   */
  async goto() {
    await this.page.goto('/');
    await this.waitForBackendConnection();
  }

  /**
   * Wait for the backend WebSocket connection to be established
   */
  async waitForBackendConnection(timeout = 15000) {
    await expect(this.connectionStatus).toHaveText('LIVE', { timeout });
    // Additional wait for capture status to update
    await this.page.waitForTimeout(1000);
  }

  /**
   * Click Start Recording and wait for session to start
   */
  async startRecording() {
    await expect(this.startRecordingButton).toBeEnabled({ timeout: 10000 });
    await this.startRecordingButton.click();
    
    // Wait for recording state - button changes to "Stop"
    await expect(this.stopRecordingButton).toBeVisible({ timeout: 10000 });
    await expect(this.timerDisplay).toBeVisible({ timeout: 5000 });
  }

  /**
   * Click Stop Recording and wait for finalization
   */
  async stopRecording() {
    await expect(this.stopRecordingButton).toBeEnabled({ timeout: 10000 });
    await this.stopRecordingButton.click();
    
    // Wait for recording to stop - button changes back to "Start Recording"
    await expect(this.startRecordingButton).toBeVisible({ timeout: 15000 });
    await expect(this.timerDisplay).toBeHidden({ timeout: 5000 });
  }

  /**
   * Send a dummy audio chunk via WebSocket (simulates capture agent)
   * This directly tests the /ws/chunks endpoint
   */
  async sendDummyAudioChunk(encounterId: string = 'e2e-test') {
    // We'll use the page's WebSocket connection or create a separate one
    // For E2E, we'll inject a script to send via the existing dashboard WS
    await this.page.evaluate(async (id) => {
      // Find the existing WebSocket connection (attached to window by the app)
      // The app uses useWebSocket hook which doesn't expose the WS directly
      // So we create a new WebSocket to /ws/chunks
      const ws = new WebSocket('ws://localhost:8766/ws/chunks');
      
      await new Promise<void>((resolve, reject) => {
        ws.onopen = () => resolve();
        ws.onerror = (err) => reject(err);
        setTimeout(() => reject(new Error('WebSocket connection timeout')), 5000);
      });

      // Send session_start
      ws.send(JSON.stringify({
        type: 'session_start',
        encounter_id: id,
      }));

      // Wait a bit for session to start
      await new Promise((r) => setTimeout(r, 500));

      // Send a dummy audio chunk (100ms of silence at 16kHz mono)
      const silence = new Int16Array(1600); // 100ms at 16kHz
      const base64 = btoa(String.fromCharCode.apply(null, new Uint8Array(silence.buffer)));
      
      ws.send(JSON.stringify({
        chunk_id: 0,
        pcm_b64: base64,
        sample_rate: 16000,
        channels: 1,
        mic_channel: 0,
        start_sample: 0,
        end_sample: 1600,
        duration_ms: 100,
        language: 'hi',
        encounter_id: id,
      }));

      // Wait for response
      const responsePromise = new Promise<any>((resolve) => {
        ws.onmessage = (event) => {
          const data = JSON.parse(event.data);
          if (data.type === 'chunk_result') {
            resolve(data);
          }
        };
      });

      // Set a timeout
      const timeoutPromise = new Promise((_, reject) => 
        setTimeout(() => reject(new Error('No chunk_result received')), 15000)
      );

      const result = await Promise.race([responsePromise, timeoutPromise]);
      ws.close();
      return result;
    }, encounterId);
  }

  /**
   * Get the current filled field count from the badge
   */
  async getFilledCount(): Promise<number> {
    const text = await this.filledCountBadge.textContent();
    const match = text?.match(/(\d+)\s+filled/);
    return match ? parseInt(match[1], 10) : 0;
  }

  /**
   * Get all visible field values from the case sheet
   */
  async getFieldValues(): Promise<Record<string, string>> {
    const fields: Record<string, string> = {};
    
    // Get all field tiles - they have the label and value
    const tiles = await this.fieldTiles.all();
    for (const tile of tiles) {
      const labelEl = tile.locator('text=/Beneficiary|Registration|Husband|RCH|Health|Block|District|IPD|BPL|Contact|ANC|Aadhaar|ASHA/').first();
      const valueEl = tile.locator('span.text-lg').first();
      
      const label = await labelEl.textContent();
      const value = await valueEl.textContent();
      
      if (label && value && value !== '—') {
        fields[label.trim()] = value.trim();
      }
    }
    return fields;
  }

  /**
   * Wait for a transcript message to appear
   */
  async waitForTranscript(timeout = 10000) {
    await expect(this.transcriptMessages.first()).toBeVisible({ timeout });
  }

  /**
   * Get transcript messages count
   */
  async getTranscriptCount(): Promise<number> {
    return await this.transcriptMessages.count();
  }

  /**
   * Take a screenshot with a descriptive name
   */
  async screenshot(name: string) {
    await this.page.screenshot({ 
      path: `test-results/screenshots/${name}.png`,
      fullPage: true 
    });
  }

  /**
   * Verify WebSocket connection indicators
   */
  async verifyConnectionState(expected: 'connected' | 'disconnected') {
    if (expected === 'connected') {
      await expect(this.connectionStatus).toHaveText('LIVE');
    } else {
      await expect(this.connectionStatus).toHaveText('OFFLINE');
    }
  }
}