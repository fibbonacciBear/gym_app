/**
 * Web Speech API integration for voice input and output.
 */
const VoiceInput = {
    recognition: null,
    isListening: false,
    onResult: null,
    onError: null,

    init() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

        if (!SpeechRecognition) {
            console.warn('Speech recognition not supported');
            return false;
        }

        this.recognition = new SpeechRecognition();
        this.recognition.continuous = false;
        this.recognition.interimResults = false;
        this.recognition.lang = 'en-US';

        this.recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            if (this.onResult) {
                this.onResult(transcript);
            }
        };

        this.recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            this.isListening = false;
            if (this.onError) {
                this.onError(event.error);
            }
        };

        this.recognition.onend = () => {
            this.isListening = false;
        };

        return true;
    },

    start() {
        if (!this.recognition) {
            if (!this.init()) {
                return false;
            }
        }

        try {
            this.recognition.start();
            this.isListening = true;
            return true;
        } catch (e) {
            console.error('Failed to start recognition:', e);
            return false;
        }
    },

    stop() {
        if (this.recognition && this.isListening) {
            this.recognition.stop();
            this.isListening = false;
        }
    }
};

/**
 * Text-to-Speech output
 */
const VoiceOutput = {
    synthesis: window.speechSynthesis,
    isSpeaking: false,
    enabled: true,
    selectedVoice: null,

    init() {
        if (!this.synthesis) return;

        // Get available voices
        const loadVoices = () => {
            const voices = this.synthesis.getVoices();

            // Prefer higher-quality voices
            // Priority: Google voices > Enhanced/Premium voices > default
            const preferredVoices = [
                'Google US English',
                'Google UK English Female',
                'Samantha',           // Mac OS
                'Karen',              // Mac OS
                'Alex',               // Mac OS
                'Microsoft Zira',     // Windows
                'Microsoft David',    // Windows
            ];

            // Try to find a preferred voice
            for (const preferred of preferredVoices) {
                const voice = voices.find(v => v.name === preferred);
                if (voice) {
                    this.selectedVoice = voice;
                    console.log('Using voice:', voice.name);
                    return;
                }
            }

            // Fallback to first English voice with good quality
            const englishVoice = voices.find(v =>
                v.lang.startsWith('en') && (
                    v.name.includes('Premium') ||
                    v.name.includes('Enhanced') ||
                    v.name.includes('Google')
                )
            );

            if (englishVoice) {
                this.selectedVoice = englishVoice;
                console.log('Using voice:', englishVoice.name);
            } else {
                // Use first available English voice
                this.selectedVoice = voices.find(v => v.lang.startsWith('en'));
                if (this.selectedVoice) {
                    console.log('Using voice:', this.selectedVoice.name);
                }
            }
        };

        // Voices might load asynchronously
        if (this.synthesis.getVoices().length > 0) {
            loadVoices();
        } else {
            this.synthesis.onvoiceschanged = loadVoices;
        }
    },

    speak(text, options = {}) {
        if (!this.synthesis || !this.enabled) {
            return false;
        }

        // Initialize if not already done
        if (!this.selectedVoice) {
            this.init();
        }

        // Cancel any ongoing speech
        this.cancel();

        const utterance = new SpeechSynthesisUtterance(text);

        // Use selected voice if available
        if (this.selectedVoice) {
            utterance.voice = this.selectedVoice;
        }

        // Configure voice settings for more natural sound
        utterance.rate = options.rate || 1.1;      // Slightly faster than default
        utterance.pitch = options.pitch || 1.0;    // Normal pitch
        utterance.volume = options.volume || 0.9;  // Slightly lower volume
        utterance.lang = options.lang || 'en-US';

        utterance.onstart = () => {
            this.isSpeaking = true;
        };

        utterance.onend = () => {
            this.isSpeaking = false;
        };

        utterance.onerror = (event) => {
            console.error('Speech synthesis error:', event.error);
            this.isSpeaking = false;
        };

        this.synthesis.speak(utterance);
        return true;
    },

    cancel() {
        if (this.synthesis && this.isSpeaking) {
            this.synthesis.cancel();
            this.isSpeaking = false;
        }
    },

    toggle() {
        this.enabled = !this.enabled;
        if (!this.enabled) {
            this.cancel();
        }
        return this.enabled;
    },

    isSupported() {
        return !!this.synthesis;
    }
};
