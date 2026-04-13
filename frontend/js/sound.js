/* =============================================
   SOUND.JS - Audio/sound effects system
   ============================================= */

import { state, persistToStorage } from './state.js';

let audioContext = null;

// Get or create AudioContext (lazy initialization)
function getAudioContext() {
    if (!audioContext) {
        try {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
        } catch (e) {
            console.warn('Web Audio API not supported');
            return null;
        }
    }

    // Resume context if suspended (needed for user gesture requirement)
    if (audioContext.state === 'suspended') {
        audioContext.resume();
    }

    return audioContext;
}

// Play sound effect
export function playSound(type) {
    if (!state.soundEnabled) return;

    try {
        const ctx = getAudioContext();
        if (!ctx) return;

        const oscillator = ctx.createOscillator();
        const gainNode = ctx.createGain();
        oscillator.connect(gainNode);
        gainNode.connect(ctx.destination);

        switch (type) {
            case 'success':
                // Happy ascending chime
                oscillator.frequency.setValueAtTime(523.25, ctx.currentTime); // C5
                oscillator.frequency.setValueAtTime(659.25, ctx.currentTime + 0.1); // E5
                oscillator.frequency.setValueAtTime(783.99, ctx.currentTime + 0.2); // G5
                oscillator.type = 'sine';
                gainNode.gain.setValueAtTime(0.15, ctx.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4);
                oscillator.start(ctx.currentTime);
                oscillator.stop(ctx.currentTime + 0.4);
                break;

            case 'error':
                // Low warning buzz
                oscillator.frequency.setValueAtTime(150, ctx.currentTime);
                oscillator.frequency.setValueAtTime(100, ctx.currentTime + 0.1);
                oscillator.type = 'sawtooth';
                gainNode.gain.setValueAtTime(0.1, ctx.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
                oscillator.start(ctx.currentTime);
                oscillator.stop(ctx.currentTime + 0.3);
                break;

            case 'warning':
                // Two-tone alert
                oscillator.frequency.setValueAtTime(440, ctx.currentTime);
                oscillator.frequency.setValueAtTime(380, ctx.currentTime + 0.15);
                oscillator.type = 'triangle';
                gainNode.gain.setValueAtTime(0.12, ctx.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
                oscillator.start(ctx.currentTime);
                oscillator.stop(ctx.currentTime + 0.3);
                break;

            case 'info':
                // Soft ping
                oscillator.frequency.setValueAtTime(880, ctx.currentTime);
                oscillator.type = 'sine';
                gainNode.gain.setValueAtTime(0.08, ctx.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15);
                oscillator.start(ctx.currentTime);
                oscillator.stop(ctx.currentTime + 0.15);
                break;

            case 'click':
                // Quick click
                oscillator.frequency.setValueAtTime(1000, ctx.currentTime);
                oscillator.type = 'sine';
                gainNode.gain.setValueAtTime(0.05, ctx.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.05);
                oscillator.start(ctx.currentTime);
                oscillator.stop(ctx.currentTime + 0.05);
                break;

            case 'complete':
                // Victory fanfare
                playCompleteSound(ctx);
                return;

            case 'download':
                // Download whoosh
                oscillator.frequency.setValueAtTime(600, ctx.currentTime);
                oscillator.frequency.exponentialRampToValueAtTime(200, ctx.currentTime + 0.3);
                oscillator.type = 'sine';
                gainNode.gain.setValueAtTime(0.1, ctx.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
                oscillator.start(ctx.currentTime);
                oscillator.stop(ctx.currentTime + 0.3);
                break;
        }
    } catch (e) {
        console.warn('Sound failed:', e);
    }
}

// Special complete sound (chord)
function playCompleteSound(ctx) {
    const osc1 = ctx.createOscillator();
    const osc2 = ctx.createOscillator();
    const osc3 = ctx.createOscillator();
    const gain1 = ctx.createGain();

    osc1.connect(gain1);
    osc2.connect(gain1);
    osc3.connect(gain1);
    gain1.connect(ctx.destination);

    osc1.frequency.value = 523.25; // C5
    osc2.frequency.value = 659.25; // E5
    osc3.frequency.value = 783.99; // G5

    osc1.type = osc2.type = osc3.type = 'sine';
    gain1.gain.setValueAtTime(0.1, ctx.currentTime);
    gain1.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.8);

    osc1.start(ctx.currentTime);
    osc2.start(ctx.currentTime + 0.1);
    osc3.start(ctx.currentTime + 0.2);
    osc1.stop(ctx.currentTime + 0.8);
    osc2.stop(ctx.currentTime + 0.8);
    osc3.stop(ctx.currentTime + 0.8);
}

// Toggle sound
export function toggleSound() {
    state.soundEnabled = !state.soundEnabled;
    persistToStorage('soundEnabled', state.soundEnabled);
    updateSoundIcon();

    if (state.soundEnabled) {
        playSound('success');
    }

    return state.soundEnabled;
}

// Update sound icon in UI
export function updateSoundIcon() {
    const onIcon = document.getElementById('sound-on-icon');
    const offIcon = document.getElementById('sound-off-icon');

    if (onIcon) onIcon.classList.toggle('hidden', !state.soundEnabled);
    if (offIcon) offIcon.classList.toggle('hidden', state.soundEnabled);
}
