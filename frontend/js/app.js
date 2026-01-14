/**
 * Main workout app using Alpine.js
 */
function workoutApp() {
    return {
        // Auth state
        isAuthenticated: false,
        user: null,
        authInitialized: false,

        // State
        activeTab: 'workout',
        currentWorkout: null,
        allExercises: [],
        workoutHistory: [],
        historyLoading: false,
        selectedWorkout: null,
        statusMessage: '',
        statusType: 'success',
        showExerciseSelector: false,
        showSetLogger: false,
        selectedExerciseId: null,
        setForm: {
            weight: '',
            reps: '',
            unit: 'kg'
        },
        templates: [],
        showSaveTemplateModal: false,
        showTemplatesModal: false,
        templateName: '',
        isListening: false,
        voiceTranscript: '',
        voiceFallback: false,
        voiceSupported: false,
        voiceOutputEnabled: true,

        // Card Mode state
        cardMode: localStorage.getItem('cardMode') === 'true',
        cardModeConfirmation: '',
        cardModeConfirmationType: '',

        // Exercise history cache (for showing previous values)
        exerciseHistoryCache: {},

        // Personal Records state
        showPRScreen: false,
        allPersonalRecords: [],
        prLoading: false,

        // Plan Builder state
        showPlanBuilder: false,
        showHistoryImport: false,
        showTemplateEditor: false,
        showExerciseSelectorForTemplate: false,
        editingTemplate: null,
        templateEditorData: {
            name: '',
            exercises: []
        },
        templateEditorVoiceActive: false,
        templatePlanMode: false,
        templatePlanModeConfirmation: '',
        templatePlanModeConfirmationType: '',

        // Initialize
        async init() {
            // Initialize Auth0
            try {
                const auth0Ready = await window.Auth.init();
                if (auth0Ready) {
                    this.isAuthenticated = await window.Auth.isAuthenticated();
                    if (this.isAuthenticated) {
                        this.user = await window.Auth.getUser();
                    }
                }
                this.authInitialized = true;
            } catch (error) {
                console.error('Auth initialization error:', error);
                this.authInitialized = true;
            }

            this.voiceSupported = VoiceInput.init();
            VoiceInput.onResult = (transcript) => {
                // Route to appropriate handler based on context
                if (this.templatePlanMode) {
                    this.handleTemplatePlanModeVoice(transcript);
                } else if (this.templateEditorVoiceActive) {
                    this.handleTemplateEditorVoice(transcript);
                } else if (this.cardMode) {
                    this.handleVoiceResultCardMode(transcript);
                } else {
                    this.handleVoiceResult(transcript);
                }
            };
            VoiceInput.onError = (error) => this.handleVoiceError(error);
            VoiceOutput.init(); // Initialize voice output
            await this.loadExercises();
            
            // Only load workout data if authenticated
            if (this.isAuthenticated) {
                await this.loadCurrentWorkout();
                await this.loadTemplates();  // Load templates for Plan Builder
            } else {
                this.showStatus('Please log in to start tracking workouts', 'info');
            }
        },

        // Auth handlers
        async handleLogin() {
            try {
                await window.Auth.login();
            } catch (error) {
                console.error('Login failed:', error);
                this.showStatus('Login failed. Please try again.', 'error');
            }
        },

        async handleLogout() {
            try {
                await window.Auth.logout();
            } catch (error) {
                console.error('Logout failed:', error);
                this.showStatus('Logout failed. Please try again.', 'error');
            }
        },

        // Load all exercises from the library
        async loadExercises() {
            try {
                this.allExercises = await API.getExercises();
            } catch (error) {
                console.error('Failed to load exercises:', error);
            }
        },

        // Load current workout from projection
        async loadCurrentWorkout() {
            try {
                this.currentWorkout = await API.getProjection('current_workout');
                // Debug: Log workout data to help diagnose set_groups issues
                if (this.currentWorkout) {
                    console.log('[DEBUG] Loaded currentWorkout:', JSON.stringify(this.currentWorkout, null, 2));
                    this.currentWorkout.exercises?.forEach(ex => {
                        console.log(`[DEBUG] Exercise ${ex.exercise_id}:`, {
                            hasTemplateTargets: !!ex.template_targets,
                            templateTargets: ex.template_targets,
                            hasSetGroups: !!ex.template_targets?.set_groups,
                            setGroupsLength: ex.template_targets?.set_groups?.length
                        });
                    });
                }
            } catch (error) {
                console.error('Failed to load current workout:', error);
            }
        },

        // Get exercise name by ID
        getExerciseName(exerciseId) {
            const exercise = this.allExercises.find(ex => ex.id === exerciseId);
            return exercise ? exercise.name : exerciseId;
        },

        // ========== GUIDED WORKOUT HELPERS ==========

        // Check if exercise has template targets (guided mode)
        hasTemplateTargets(exercise) {
            if (!exercise.template_targets) return false;
            // Check for set_groups or single target
            return this.usesSetGroups(exercise) || exercise.template_targets.target_sets > 0;
        },

        // Check if exercise uses set groups (new format)
        usesSetGroups(exercise) {
            return exercise.template_targets?.set_groups &&
                   exercise.template_targets.set_groups.length > 0;
        },

        // Generate planned sets array for display (handles both old and new formats)
        getPlannedSets(exercise) {
            if (!this.hasTemplateTargets(exercise)) return [];

            // NEW: Set groups format
            if (this.usesSetGroups(exercise)) {
                return this.getPlannedSetsFromGroups(exercise);
            }

            // OLD: Single target format (backward compat)
            const targets = exercise.template_targets;
            const plannedSets = [];

            // Defensive: ensure target_sets is a valid positive number (default to 1)
            const numSets = (targets.target_sets > 0) ? targets.target_sets : 1;
            for (let i = 0; i < numSets; i++) {
                plannedSets.push({
                    setNumber: i + 1,
                    targetWeight: targets.target_weight,
                    targetReps: targets.target_reps,
                    targetUnit: targets.target_unit || 'kg',
                    setType: targets.set_type || 'standard',
                    isFirstInGroup: i === 0,
                    groupName: null
                });
            }

            return plannedSets;
        },

        // Generate flat array of planned sets from set groups
        getPlannedSetsFromGroups(exercise) {
            if (!this.usesSetGroups(exercise)) return [];

            const plannedSets = [];
            let globalSetNumber = 1;

            exercise.template_targets.set_groups.forEach((group, groupIndex) => {
                // Defensive: ensure target_sets is a valid positive number (default to 1)
                const numSets = (group.target_sets > 0) ? group.target_sets : 1;
                for (let i = 0; i < numSets; i++) {
                    plannedSets.push({
                        setNumber: globalSetNumber++,
                        groupIndex: groupIndex,
                        groupName: group.notes || group.set_type || `Group ${groupIndex + 1}`,
                        targetWeight: group.target_weight,
                        targetReps: group.target_reps,
                        targetUnit: group.target_unit || 'kg',
                        setType: group.set_type || 'working',
                        isFirstInGroup: i === 0
                    });
                }
            });

            return plannedSets;
        },

        // Get the next planned set to log (for quick logging)
        getNextPlannedSet(exercise) {
            const plannedSets = this.getPlannedSets(exercise);
            const completedCount = exercise.sets?.length || 0;
            return plannedSets[completedCount] || null;
        },

        // Get logged set for a specific planned set number
        getLoggedSetForPlannedSet(exercise, setNumber) {
            if (!exercise.sets || setNumber > exercise.sets.length) return null;
            return exercise.sets[setNumber - 1];
        },

        // Check if a planned set is completed
        isPlannedSetCompleted(exercise, setNumber) {
            return setNumber <= (exercise.sets?.length || 0);
        },

        // Quick-log a set (checkbox click) - logs with target values from the next planned set
        async quickLogPlannedSet(exerciseId) {
            if (!this.currentWorkout) return;

            const exercise = this.currentWorkout.exercises.find(ex => ex.exercise_id === exerciseId);
            if (!exercise || !exercise.template_targets) return;

            // Get the next planned set to determine weight/reps
            const nextPlannedSet = this.getNextPlannedSet(exercise);
            if (!nextPlannedSet) return;

            // Validate that weight and reps are defined for quick-logging
            if (!nextPlannedSet.targetWeight || nextPlannedSet.targetWeight <= 0) {
                this.showStatus('Cannot quick-log: target weight not set. Use manual entry.', 'error');
                return;
            }
            if (!nextPlannedSet.targetReps || nextPlannedSet.targetReps <= 0) {
                this.showStatus('Cannot quick-log: target reps not set. Use manual entry.', 'error');
                return;
            }

            try {
                const result = await API.emitEvent('SetLogged', {
                    workout_id: this.currentWorkout.id,
                    exercise_id: exerciseId,
                    weight: nextPlannedSet.targetWeight,
                    reps: nextPlannedSet.targetReps,
                    unit: nextPlannedSet.targetUnit || 'kg'
                });

                // Check for PR
                if (result.derived && result.derived.is_pr) {
                    const prType = result.derived.pr_type;
                    let prMessage = '🏆 NEW PR! Set logged!';
                    if (prType === 'weight') {
                        prMessage = '🏆 NEW MAX WEIGHT PR! Set logged!';
                    } else if (prType === 'volume') {
                        prMessage = '🏆 NEW VOLUME PR! Set logged!';
                    } else if (prType === 'estimated-1rm') {
                        prMessage = '🏆 NEW ESTIMATED 1RM PR! Set logged!';
                    } else if (prType && prType.includes('-rep')) {
                        prMessage = `🏆 NEW ${prType.toUpperCase()} PR! Set logged!`;
                    }
                    this.showStatus(prMessage, 'success');
                    delete this.exerciseHistoryCache[exerciseId];
                } else {
                    this.showStatus('Set logged!', 'success');
                }

                await this.loadCurrentWorkout();
            } catch (error) {
                this.showStatus('Failed to log set: ' + error.message, 'error');
            }
        },

        // ========== TEMPLATE EDITOR SET GROUPS HELPERS ==========

        // Add set group to exercise in template editor
        addSetGroupToExercise(exerciseIndex) {
            const exercise = this.templateEditorData.exercises[exerciseIndex];

            // Initialize set_groups array if needed
            const currentGroups = exercise.set_groups || [];

            // Add new group with defaults
            const newGroups = [...currentGroups, {
                target_sets: 3,
                target_reps: 10,
                target_weight: null,
                target_unit: 'kg',
                set_type: 'working',
                rest_seconds: 60,
                notes: ''
            }];

            // Replace entire exercise object to trigger Alpine reactivity
            this.templateEditorData.exercises[exerciseIndex] = {
                ...exercise,
                set_groups: newGroups
            };
        },

        // Convert single-target to set groups format
        convertToSetGroups(exerciseIndex) {
            const exercise = this.templateEditorData.exercises[exerciseIndex];

            // Create initial group from existing values
            const newSetGroups = [{
                target_sets: exercise.target_sets || 3,
                target_reps: exercise.target_reps || 10,
                target_weight: exercise.target_weight || null,
                target_unit: exercise.target_unit || 'kg',
                set_type: 'working',
                rest_seconds: exercise.rest_seconds || 60,
                notes: 'Working Sets'
            }];

            // Replace entire exercise object to trigger Alpine reactivity
            this.templateEditorData.exercises[exerciseIndex] = {
                ...exercise,
                set_groups: newSetGroups
            };
        },

        // Remove set group from exercise
        removeSetGroup(exerciseIndex, groupIndex) {
            const exercise = this.templateEditorData.exercises[exerciseIndex];
            if (exercise.set_groups) {
                const newGroups = exercise.set_groups.filter((_, i) => i !== groupIndex);
                // Replace entire exercise object to trigger Alpine reactivity
                this.templateEditorData.exercises[exerciseIndex] = {
                    ...exercise,
                    set_groups: newGroups.length > 0 ? newGroups : null
                };
            }
        },

        // ========== END GUIDED WORKOUT HELPERS ==========

        // Start a new workout (legacy - kept for backwards compat)
        async startWorkout() {
            try {
                const result = await API.emitEvent('WorkoutStarted', {});
                this.showStatus('Workout started!', 'success');
                await this.loadCurrentWorkout();
            } catch (error) {
                this.showStatus('Failed to start workout: ' + error.message, 'error');
            }
        },

        // Get subtitle for Today's Workout button
        getTodaysWorkoutSubtitle() {
            if (this.templates.length === 0) {
                return "No plan yet – tap to create";
            }
            // For now, just show template count - later can show scheduled workout
            return `${this.templates.length} template${this.templates.length > 1 ? 's' : ''} available`;
        },

        // Start Today's Workout (shows template selection or Plan Builder)
        async startTodaysWorkout() {
            if (this.templates.length === 0) {
                // No templates - open plan builder
                this.openPlanBuilder();
            } else {
                // Show template selection modal
                this.showTemplatesModal = true;
            }
        },

        // Quick Start - immediate ad-hoc workout
        async startQuickWorkout() {
            try {
                await API.emitEvent('WorkoutStarted', {});
                this.showStatus('Workout started!', 'success');
                await this.loadCurrentWorkout();
            } catch (error) {
                this.showStatus('Failed to start workout: ' + error.message, 'error');
            }
        },

        // Open Plan Builder modal
        openPlanBuilder() {
            this.showPlanBuilder = true;
        },

        // Open Template Editor (for new or existing template)
        openTemplateEditor(template) {
            this.showPlanBuilder = false;
            this.editingTemplate = template;

            if (template) {
                // Editing existing template
                this.templateEditorData = {
                    name: template.name,
                    exercises: (template.exercises || []).map(ex => ({
                        exercise_id: ex.exercise_id,
                        target_sets: ex.target_sets || null,
                        target_reps: ex.target_reps || null,
                        target_weight: ex.target_weight || null,
                        target_unit: ex.target_unit || 'kg',
                        set_type: ex.set_type || 'standard',
                        rest_seconds: ex.rest_seconds || 60,
                        set_groups: ex.set_groups || null  // Preserve set groups if they exist
                    }))
                };
            } else {
                // Creating new template
                this.templateEditorData = {
                    name: '',
                    exercises: []
                };
            }

            this.showTemplateEditor = true;
        },

        // Import workout from history as a template
        importWorkoutAsTemplate(workout) {
            this.showHistoryImport = false;
            this.showPlanBuilder = false;
            this.editingTemplate = null;

            // Convert workout exercises to template format
            const exercises = workout.exercises.map(ex => {
                // Calculate average weight and reps from the sets
                let avgWeight = null;
                let avgReps = null;
                if (ex.sets && ex.sets.length > 0) {
                    avgWeight = ex.sets.reduce((sum, s) => sum + (s.weight || 0), 0) / ex.sets.length;
                    avgReps = Math.round(ex.sets.reduce((sum, s) => sum + (s.reps || 0), 0) / ex.sets.length);
                    // Round weight to nearest 0.5
                    avgWeight = Math.round(avgWeight * 2) / 2;
                }

                return {
                    exercise_id: ex.exercise_id,
                    target_sets: ex.sets?.length || null,
                    target_reps: avgReps,
                    target_weight: avgWeight,
                    target_unit: ex.sets?.[0]?.unit || 'kg',
                    set_type: 'standard',
                    rest_seconds: 60,
                    set_groups: null  // Initialize for Alpine.js reactivity
                };
            });

            this.templateEditorData = {
                name: `Workout from ${this.formatDate(workout.completed_at)}`,
                exercises: exercises
            };

            this.showTemplateEditor = true;
        },

        // Add exercise to template being edited
        addExerciseToTemplate(exerciseId) {
            // Check if already in template
            if (this.templateEditorData.exercises.some(ex => ex.exercise_id === exerciseId)) {
                this.showStatus('Exercise already in template', 'error');
                return;
            }

            this.templateEditorData.exercises.push({
                exercise_id: exerciseId,
                target_sets: 3,  // Default values
                target_reps: 10,
                target_weight: null,
                target_unit: 'kg',
                set_type: 'standard',
                rest_seconds: 60,
                set_groups: null  // Initialize for Alpine.js reactivity
            });

            this.showExerciseSelectorForTemplate = false;
        },

        // Remove exercise from template being edited
        removeExerciseFromTemplate(index) {
            this.templateEditorData.exercises.splice(index, 1);
        },

        // Save template (create or update)
        async saveTemplate() {
            if (!this.templateEditorData.name.trim()) {
                this.showStatus('Please enter a template name', 'error');
                return;
            }

            // Check for duplicate name (case-insensitive)
            const nameLower = this.templateEditorData.name.trim().toLowerCase();
            const duplicate = this.templates.find(t =>
                t.name.trim().toLowerCase() === nameLower &&
                (!this.editingTemplate || t.id !== this.editingTemplate.id)
            );
            if (duplicate) {
                this.showStatus('A template with this name already exists', 'error');
                return;
            }

            if (this.templateEditorData.exercises.length === 0) {
                this.showStatus('Please add at least one exercise', 'error');
                return;
            }

            try {
                const payload = {
                    name: this.templateEditorData.name.trim(),
                    exercises: this.templateEditorData.exercises.map(ex => ({
                        exercise_id: ex.exercise_id,
                        target_sets: ex.target_sets || null,
                        target_reps: ex.target_reps || null,
                        target_weight: ex.target_weight || null,
                        target_unit: ex.target_unit || 'kg',
                        set_type: ex.set_type || 'standard',
                        rest_seconds: ex.rest_seconds || 60,
                        set_groups: ex.set_groups || null  // Include set groups if present
                    }))
                };
                console.log('[DEBUG] Saving template with payload:', JSON.stringify(payload, null, 2));

                if (this.editingTemplate) {
                    // Update existing template
                    const headers = await API.getHeaders();
                    const response = await fetch(`/api/templates/${this.editingTemplate.id}`, {
                        method: 'PUT',
                        headers,
                        body: JSON.stringify(payload)
                    });

                    if (!response.ok) {
                        const text = await response.text();
                        try {
                            const error = JSON.parse(text);
                            throw new Error(error.detail || 'Failed to update template');
                        } catch (e) {
                            if (e.message && !e.message.includes('JSON')) throw e;
                            throw new Error(`Server error (${response.status})`);
                        }
                    }
                    this.showStatus('Template updated!', 'success');
                } else {
                    // Create new template
                    const headers = await API.getHeaders();
                    const response = await fetch('/api/templates', {
                        method: 'POST',
                        headers,
                        body: JSON.stringify(payload)
                    });

                    if (!response.ok) {
                        const text = await response.text();
                        try {
                            const error = JSON.parse(text);
                            throw new Error(error.detail || 'Failed to create template');
                        } catch (e) {
                            if (e.message && !e.message.includes('JSON')) throw e;
                            throw new Error(`Server error (${response.status})`);
                        }
                    }
                    this.showStatus('Template created!', 'success');
                }

                this.showTemplateEditor = false;
                this.templatePlanMode = false;
                this.templateEditorVoiceActive = false;
                await this.loadTemplates();
            } catch (error) {
                console.error('Failed to save template:', error);
                this.showStatus(error.message || 'Failed to save template', 'error');
            }
        },

        // Delete template
        async deleteTemplate(templateId) {
            if (!confirm('Delete this template? This cannot be undone.')) {
                return;
            }

            try {
                const headers = await API.getHeaders();
                const response = await fetch(`/api/templates/${templateId}`, {
                    method: 'DELETE',
                    headers
                });

                if (!response.ok) {
                    const text = await response.text();
                    try {
                        const error = JSON.parse(text);
                        throw new Error(error.detail || 'Failed to delete template');
                    } catch (e) {
                        if (e.message && !e.message.includes('JSON')) throw e;
                        throw new Error(`Server error (${response.status})`);
                    }
                }

                this.showStatus('Template deleted', 'success');
                this.showTemplateEditor = false;
                this.templatePlanMode = false;
                this.templateEditorVoiceActive = false;
                await this.loadTemplates();
            } catch (error) {
                console.error('Failed to delete template:', error);
                this.showStatus(error.message || 'Failed to delete template', 'error');
            }
        },

        // Toggle voice for template editor
        toggleTemplateVoice() {
            if (this.isListening) {
                VoiceInput.stop();
                this.isListening = false;
                this.templateEditorVoiceActive = false;
            } else {
                if (VoiceInput.start()) {
                    this.isListening = true;
                    this.templateEditorVoiceActive = true;
                    this.voiceTranscript = '';
                } else {
                    this.showStatus('Voice not supported', 'error');
                }
            }
        },

        // Handle voice input for template editor
        async handleTemplateEditorVoice(transcript) {
            this.isListening = false;
            this.voiceTranscript = transcript;

            try {
                // Send to voice API with plan_builder mode
                const headers = await API.getHeaders();
                const response = await fetch('/api/voice/process', {
                    method: 'POST',
                    headers,
                    body: JSON.stringify({
                        transcript,
                        mode: 'plan_builder'
                    })
                });

                const result = await response.json();

                if (result.success && result.action === 'emit') {
                    // event_result contains { event_type, payload } in plan_builder mode
                    const eventResult = result.event_result;
                    const eventType = eventResult?.event_type;
                    const payload = eventResult?.payload;

                    // Handle template-specific actions
                    if (eventType === 'ExerciseAdded' || eventType === 'SetLogged') {
                        // Extract exercise info from the response
                        const exerciseId = payload?.exercise_id;
                        if (exerciseId) {
                            // Check if exercise already in template
                            const exists = this.templateEditorData.exercises.some(
                                ex => ex.exercise_id === exerciseId
                            );

                            if (!exists) {
                                // Add exercise with any target values from voice
                                this.templateEditorData.exercises.push({
                                    exercise_id: exerciseId,
                                    target_sets: payload?.target_sets || 3,
                                    target_reps: payload?.reps || payload?.target_reps || 10,
                                    target_weight: payload?.weight || payload?.target_weight || null,
                                    target_unit: payload?.unit || 'kg',
                                    set_type: 'standard',
                                    rest_seconds: 60,
                                    set_groups: null  // Initialize for Alpine.js reactivity
                                });
                                this.showStatus(`Added ${this.getExerciseName(exerciseId)}`, 'success');
                            } else {
                                // Update existing exercise targets
                                const ex = this.templateEditorData.exercises.find(
                                    e => e.exercise_id === exerciseId
                                );
                                if (payload?.target_sets || payload?.reps || payload?.weight) {
                                    ex.target_sets = payload?.target_sets || ex.target_sets;
                                    ex.target_reps = payload?.reps || payload?.target_reps || ex.target_reps;
                                    ex.target_weight = payload?.weight || payload?.target_weight || ex.target_weight;
                                    ex.target_unit = payload?.unit || ex.target_unit;
                                    this.showStatus(`Updated ${this.getExerciseName(exerciseId)}`, 'success');
                                } else {
                                    this.showStatus('Exercise already in template', 'error');
                                }
                            }
                        }
                    }

                    // Speak confirmation
                    if (this.voiceOutputEnabled && VoiceOutput.isSupported()) {
                        VoiceOutput.speak(result.message || 'Got it');
                    }
                } else if (result.message) {
                    // LLM gave a text response (clarification needed)
                    this.showStatus(result.message, 'success');
                    if (this.voiceOutputEnabled && VoiceOutput.isSupported()) {
                        VoiceOutput.speak(result.message);
                    }
                }

                // Clear transcript after short delay
                setTimeout(() => {
                    this.voiceTranscript = '';
                }, 2000);

            } catch (error) {
                console.error('Template voice error:', error);
                this.showStatus('Voice processing failed', 'error');
            }
        },

        // Cancel template editor and go back
        cancelTemplateEditor() {
            this.showTemplateEditor = false;
            this.templatePlanMode = false;
            this.templateEditorVoiceActive = false;
            if (this.isListening) {
                VoiceInput.stop();
                this.isListening = false;
            }
            // Go back to plan builder if we were creating, otherwise just close
            if (!this.editingTemplate) {
                this.showPlanBuilder = true;
            }
        },

        // Toggle Template Plan Mode (full screen voice mode for templates)
        toggleTemplatePlanMode() {
            this.templatePlanMode = !this.templatePlanMode;
            if (this.templatePlanMode) {
                // Entering plan mode
                this.templateEditorVoiceActive = false; // Use plan mode handler instead
            } else {
                // Exiting plan mode
                if (this.isListening) {
                    VoiceInput.stop();
                    this.isListening = false;
                }
                this.templatePlanModeConfirmation = '';
                this.voiceTranscript = '';
                this.voiceFallback = false;
            }
        },

        exitTemplatePlanMode() {
            this.templatePlanMode = false;
            if (this.isListening) {
                VoiceInput.stop();
                this.isListening = false;
            }
            this.templatePlanModeConfirmation = '';
            this.voiceTranscript = '';
            this.voiceFallback = false;
        },

        // Tap to speak in template plan mode
        templatePlanModeTapToSpeak() {
            if (this.isListening) {
                VoiceInput.stop();
                this.isListening = false;
            } else {
                if (VoiceInput.start()) {
                    this.isListening = true;
                    this.voiceTranscript = '';
                    this.voiceFallback = false;
                    this.templatePlanModeConfirmation = '';
                } else {
                    this.showTemplatePlanConfirmation('Mic unavailable. Check permissions.', 'error');
                }
            }
        },

        // Show confirmation in template plan mode
        showTemplatePlanConfirmation(message, type = 'success') {
            this.templatePlanModeConfirmation = message;
            this.templatePlanModeConfirmationType = type;
            setTimeout(() => {
                this.templatePlanModeConfirmation = '';
            }, 2500);
        },

        // Handle voice result in template plan mode
        async handleTemplatePlanModeVoice(transcript) {
            this.voiceFallback = false;
            this.voiceTranscript = '';
            this.isListening = false;
            this.voiceTranscript = transcript;

            try {
                const headers = await API.getHeaders();
                const response = await fetch('/api/voice/process', {
                    method: 'POST',
                    headers,
                    body: JSON.stringify({
                        transcript,
                        mode: 'plan_builder'
                    })
                });

                const result = await response.json();

                if (result.success && result.action === 'emit') {
                    const eventResult = result.event_result;
                    const eventType = eventResult?.event_type;
                    const payload = eventResult?.payload;

                    if (eventType === 'ExerciseAdded' || eventType === 'SetLogged') {
                        const exerciseId = payload?.exercise_id;
                        if (exerciseId) {
                            const exists = this.templateEditorData.exercises.some(
                                ex => ex.exercise_id === exerciseId
                            );

                            if (!exists) {
                                this.templateEditorData.exercises.push({
                                    exercise_id: exerciseId,
                                    target_sets: payload?.target_sets || 3,
                                    target_reps: payload?.reps || payload?.target_reps || 10,
                                    target_weight: payload?.weight || payload?.target_weight || null,
                                    target_unit: payload?.unit || 'kg',
                                    set_type: 'standard',
                                    rest_seconds: 60,
                                    set_groups: null  // Initialize for Alpine.js reactivity
                                });

                                const msg = `Added ${this.getExerciseName(exerciseId)}`;
                                this.showTemplatePlanConfirmation(msg, 'success');

                                if (this.voiceOutputEnabled && VoiceOutput.isSupported()) {
                                    VoiceOutput.speak(msg);
                                }
                            } else {
                                // Update existing
                                const ex = this.templateEditorData.exercises.find(
                                    e => e.exercise_id === exerciseId
                                );
                                if (payload?.target_sets || payload?.reps || payload?.weight) {
                                    ex.target_sets = payload?.target_sets || ex.target_sets;
                                    ex.target_reps = payload?.reps || payload?.target_reps || ex.target_reps;
                                    ex.target_weight = payload?.weight || payload?.target_weight || ex.target_weight;
                                    ex.target_unit = payload?.unit || ex.target_unit;

                                    const msg = `Updated ${this.getExerciseName(exerciseId)}`;
                                    this.showTemplatePlanConfirmation(msg, 'success');

                                    if (this.voiceOutputEnabled && VoiceOutput.isSupported()) {
                                        VoiceOutput.speak(msg);
                                    }
                                } else {
                                    this.showTemplatePlanConfirmation('Already in template', 'error');
                                }
                            }
                        }
                    }

                    this.voiceTranscript = '';
                } else if (result.message) {
                    this.showTemplatePlanConfirmation(result.message, 'success');
                    if (this.voiceOutputEnabled && VoiceOutput.isSupported()) {
                        VoiceOutput.speak(result.message);
                    }
                } else if (result.fallback) {
                    this.voiceFallback = true;
                    this.showTemplatePlanConfirmation('Could not process', 'error');
                }
            } catch (error) {
                console.error('Template plan mode voice error:', error);
                this.showTemplatePlanConfirmation('Failed to process', 'error');
                this.voiceFallback = true;
            }
        },

        // Add exercise to workout
        async addExercise(exerciseId) {
            if (!this.currentWorkout) return;

            try {
                await API.emitEvent('ExerciseAdded', {
                    workout_id: this.currentWorkout.id,
                    exercise_id: exerciseId
                });
                this.showExerciseSelector = false;
                this.showStatus('Exercise added!', 'success');
                await this.loadCurrentWorkout();
            } catch (error) {
                this.showStatus('Failed to add exercise: ' + error.message, 'error');
            }
        },

        // Fetch exercise history (with cache)
        async fetchExerciseHistory(exerciseId) {
            if (this.exerciseHistoryCache[exerciseId]) {
                return this.exerciseHistoryCache[exerciseId];
            }
            try {
                const response = await fetch(`/api/exercises/${exerciseId}/history`);
                if (response.ok) {
                    const data = await response.json();
                    this.exerciseHistoryCache[exerciseId] = data;
                    return data;
                }
            } catch (error) {
                console.error('Failed to fetch exercise history:', error);
            }
            return null;
        },

        // Get previous session info for an exercise
        getPreviousSession(exerciseId) {
            const cached = this.exerciseHistoryCache[exerciseId];
            return cached?.last_session || null;
        },

        // Get PR info for an exercise
        getPersonalRecords(exerciseId) {
            const cached = this.exerciseHistoryCache[exerciseId];
            return cached?.personal_records || null;
        },

        // Select exercise to log a set
        async selectExerciseForSet(exerciseId) {
            this.selectedExerciseId = exerciseId;

            // Fetch exercise history for previous values
            await this.fetchExerciseHistory(exerciseId);

            // Prefill with last set values if available (from current workout first)
            const exercise = this.currentWorkout.exercises.find(ex => ex.exercise_id === exerciseId);
            if (exercise && exercise.sets.length > 0) {
                const lastSet = exercise.sets[exercise.sets.length - 1];
                this.setForm.weight = lastSet.weight;
                this.setForm.reps = lastSet.reps;
                this.setForm.unit = lastSet.unit;
            } else {
                // Try previous session
                const prevSession = this.getPreviousSession(exerciseId);
                if (prevSession && prevSession.sets && prevSession.sets.length > 0) {
                    const lastSet = prevSession.sets[0];
                    this.setForm.weight = lastSet.weight;
                    this.setForm.reps = lastSet.reps;
                    this.setForm.unit = lastSet.unit || 'kg';
                } else {
                    this.setForm.weight = '';
                    this.setForm.reps = '';
                    this.setForm.unit = 'kg';
                }
            }

            this.showSetLogger = true;
        },

        // Log a set
        async logSet() {
            if (!this.currentWorkout) return;

            // Client-side validation
            const weight = parseFloat(this.setForm.weight);
            const reps = parseInt(this.setForm.reps);

            if (!this.setForm.weight || isNaN(weight) || weight <= 0) {
                this.showStatus('Please enter a valid weight', 'error');
                return;
            }

            if (!this.setForm.reps || isNaN(reps) || reps <= 0) {
                this.showStatus('Please enter valid reps', 'error');
                return;
            }

            try {
                const result = await API.emitEvent('SetLogged', {
                    workout_id: this.currentWorkout.id,
                    exercise_id: this.selectedExerciseId,
                    weight: weight,
                    reps: reps,
                    unit: this.setForm.unit
                });
                this.showSetLogger = false;

                // Check for PR
                if (result.derived && result.derived.is_pr) {
                    const prType = result.derived.pr_type;
                    let prMessage = '🏆 NEW PR! Set logged!';
                    if (prType === 'weight') {
                        prMessage = '🏆 NEW MAX WEIGHT PR! Set logged!';
                    } else if (prType === 'volume') {
                        prMessage = '🏆 NEW VOLUME PR! Set logged!';
                    } else if (prType === 'estimated-1rm') {
                        prMessage = '🏆 NEW ESTIMATED 1RM PR! Set logged!';
                    } else if (prType && prType.includes('-rep')) {
                        prMessage = `🏆 NEW ${prType.toUpperCase()} PR! Set logged!`;
                    }
                    this.showStatus(prMessage, 'success');
                    // Invalidate cache so next fetch gets updated PR
                    delete this.exerciseHistoryCache[this.selectedExerciseId];
                } else {
                    this.showStatus('Set logged!', 'success');
                }

                await this.loadCurrentWorkout();
            } catch (error) {
                this.showStatus('Failed to log set: ' + error.message, 'error');
            }
        },

        // Delete a set
        async deleteSet(eventId) {
            if (!this.currentWorkout) return;

            if (!eventId) {
                this.showStatus('Cannot delete legacy set. Finish workout to clear.', 'error');
                return;
            }

            // Confirm before deleting to prevent accidental data loss
            if (!confirm('Delete this set? This cannot be undone.')) {
                return;
            }

            try {
                await API.emitEvent('SetDeleted', {
                    workout_id: this.currentWorkout.id,
                    original_event_id: eventId
                });
                this.showStatus('Set deleted', 'success');
                await this.loadCurrentWorkout();
            } catch (error) {
                this.showStatus('Failed to delete set: ' + error.message, 'error');
            }
        },

        // Finish the current workout
        async finishWorkout() {
            if (!this.currentWorkout) return;

            try {
                await API.emitEvent('WorkoutCompleted', {
                    workout_id: this.currentWorkout.id
                });
                this.showStatus('Workout saved!', 'success');
                await this.loadCurrentWorkout();
            } catch (error) {
                this.showStatus('Failed to finish workout: ' + error.message, 'error');
            }
        },

        // Discard the current workout
        async discardWorkout() {
            if (!this.currentWorkout) return;

            if (!confirm('Discard this workout? All data will be lost.')) {
                return;
            }

            try {
                await API.emitEvent('WorkoutDiscarded', {
                    workout_id: this.currentWorkout.id
                });
                this.showStatus('Workout discarded', 'success');
                await this.loadCurrentWorkout();
            } catch (error) {
                this.showStatus('Failed to discard workout: ' + error.message, 'error');
            }
        },

        // Show status message
        showStatus(message, type = 'success') {
            this.statusMessage = message;
            this.statusType = type;
            setTimeout(() => {
                this.statusMessage = '';
            }, 3000);
        },

        // Load workout history
        async loadHistory() {
            this.historyLoading = true;
            try {
                const headers = await API.getHeaders();
                const response = await fetch('/api/history', { headers });
                if (!response.ok) {
                    throw new Error('Failed to load history');
                }
                this.workoutHistory = await response.json();
            } catch (error) {
                console.error('Failed to load history:', error);
                this.showStatus('Failed to load history', 'error');
            }
            this.historyLoading = false;
        },

        // Format date for display
        formatDate(isoString) {
            if (!isoString) return '';
            const date = new Date(isoString);
            return date.toLocaleDateString('en-US', {
                weekday: 'short',
                month: 'short',
                day: 'numeric',
                year: 'numeric'
            });
        },

        // Format volume for display
        formatVolume(volume) {
            if (!volume) return '0 kg';
            if (volume >= 1000) {
                return (volume / 1000).toFixed(1) + 'k kg';
            }
            return Math.round(volume) + ' kg';
        },

        // Load templates
        async loadTemplates() {
            try {
                const headers = await API.getHeaders();
                const response = await fetch('/api/templates', { headers });
                if (!response.ok) {
                    throw new Error('Failed to load templates');
                }
                this.templates = await response.json();
            } catch (error) {
                console.error('Failed to load templates:', error);
                this.showStatus('Failed to load templates', 'error');
            }
        },

        // Load all personal records
        async loadPersonalRecords() {
            this.prLoading = true;
            try {
                const headers = await API.getHeaders();
                const response = await fetch('/api/personal-records', { headers });
                if (!response.ok) {
                    throw new Error('Failed to load personal records');
                }
                const data = await response.json();
                this.allPersonalRecords = data.records || [];
            } catch (error) {
                console.error('Failed to load personal records:', error);
                this.showStatus('Failed to load personal records', 'error');
            } finally {
                this.prLoading = false;
            }
        },

        // Open Personal Records screen
        async openPRScreen() {
            this.showPRScreen = true;
            await this.loadPersonalRecords();
        },

        // Format date for display
        formatPRDate(dateStr) {
            if (!dateStr) return '';
            return new Date(dateStr).toLocaleDateString();
        },

        // Save current workout as a template
        async saveAsTemplate() {
            if (!this.templateName.trim() || !this.currentWorkout) {
                this.showStatus('Please enter a template name', 'error');
                return;
            }

            // Convert workout exercises to template format with targets
            const exercises = this.currentWorkout.exercises.map(ex => {
                const avgWeight = ex.sets?.length ?
                    ex.sets.reduce((sum, s) => sum + (s.weight || 0), 0) / ex.sets.length : null;
                const avgReps = ex.sets?.length ?
                    Math.round(ex.sets.reduce((sum, s) => sum + (s.reps || 0), 0) / ex.sets.length) : 10;

                return {
                    exercise_id: ex.exercise_id,
                    target_sets: ex.sets?.length || 3,
                    target_reps: avgReps,
                    target_weight: avgWeight,
                    target_unit: ex.sets?.[0]?.unit || 'kg',
                    set_type: 'standard',
                    rest_seconds: 60
                };
            });

            try {
                const headers = await API.getHeaders();
                const response = await fetch('/api/templates', {
                    method: 'POST',
                    headers,
                    body: JSON.stringify({
                        name: this.templateName.trim(),
                        exercises: exercises  // Use full exercise format with targets
                    })
                });

                if (!response.ok) {
                    const text = await response.text();
                    try {
                        const error = JSON.parse(text);
                        throw new Error(error.detail || 'Failed to save template');
                    } catch (e) {
                        if (e.message && !e.message.includes('JSON')) throw e;
                        throw new Error(`Server error (${response.status})`);
                    }
                }

                this.showStatus('Template saved!', 'success');
                this.showSaveTemplateModal = false;
                this.templateName = '';
                await this.loadTemplates();
            } catch (error) {
                console.error('Failed to save template:', error);
                this.showStatus(error.message || 'Failed to save template', 'error');
            }
        },

        // Start a workout from a template
        async startFromTemplate(templateId) {
            try {
                const headers = await API.getHeaders();
                const response = await fetch(`/api/templates/${templateId}/start`, {
                    method: 'POST',
                    headers
                });

                if (!response.ok) {
                    throw new Error('Failed to start from template');
                }

                await this.loadCurrentWorkout();
                this.showTemplatesModal = false;
                this.showStatus('Workout started from template!', 'success');
            } catch (error) {
                console.error('Failed to start from template:', error);
                this.showStatus('Failed to start from template', 'error');
            }
        },

        // Voice Methods
        toggleVoice() {
            if (this.isListening) {
                VoiceInput.stop();
                this.isListening = false;
            } else {
                if (VoiceInput.start()) {
                    this.isListening = true;
                    this.voiceTranscript = '';
                    this.voiceFallback = false;
                } else {
                    this.showStatus('Voice not supported in this browser', 'error');
                }
            }
        },

        async handleVoiceResult(transcript) {
            this.isListening = false;
            this.voiceTranscript = transcript;

            try {
                const headers = await API.getHeaders();
                const response = await fetch('/api/voice/process', {
                    method: 'POST',
                    headers,
                    body: JSON.stringify({transcript})
                });

                const result = await response.json();

                if (result.success) {
                    // Check for PR in event result
                    let message = result.message;
                    if (result.event_result?.derived?.is_pr) {
                        message = 'NEW PR! ' + message;
                    }

                    this.showStatus(message, 'success');

                    // Speak the response
                    if (this.voiceOutputEnabled && VoiceOutput.isSupported()) {
                        VoiceOutput.speak(message);
                    }

                    this.voiceTranscript = '';
                    await this.loadCurrentWorkout();
                } else if (result.fallback) {
                    this.voiceFallback = true;
                    const errorMsg = 'Could not process. Please try again or enter manually.';
                    this.showStatus(errorMsg, 'error');

                    if (this.voiceOutputEnabled && VoiceOutput.isSupported()) {
                        VoiceOutput.speak('Could not process');
                    }
                } else {
                    this.showStatus(result.message, 'error');

                    if (this.voiceOutputEnabled && VoiceOutput.isSupported()) {
                        VoiceOutput.speak('Error: ' + result.message);
                    }
                }
            } catch (error) {
                const errorMsg = 'Failed to process voice command';
                this.showStatus(errorMsg, 'error');
                this.voiceFallback = true;

                if (this.voiceOutputEnabled && VoiceOutput.isSupported()) {
                    VoiceOutput.speak(errorMsg);
                }
            }
        },

        handleVoiceError(error) {
            this.isListening = false;
            this.showStatus('Voice error: ' + error, 'error');
        },

        retryVoice() {
            this.voiceTranscript = '';
            this.voiceFallback = false;
            this.toggleVoice();
        },

        clearVoice() {
            this.voiceTranscript = '';
            this.voiceFallback = false;
        },

        toggleVoiceOutput() {
            this.voiceOutputEnabled = !this.voiceOutputEnabled;
            VoiceOutput.enabled = this.voiceOutputEnabled;

            const status = this.voiceOutputEnabled ? 'Voice output enabled' : 'Voice output disabled';
            this.showStatus(status, 'success');

            // Announce the change
            if (this.voiceOutputEnabled && VoiceOutput.isSupported()) {
                VoiceOutput.speak(status);
            }
        },

        // Card Mode Methods
        toggleCardMode() {
            this.cardMode = !this.cardMode;
            localStorage.setItem('cardMode', this.cardMode);

            if (this.cardMode) {
                // Enter card mode - clear any modals
                this.showExerciseSelector = false;
                this.showSetLogger = false;
                this.showSaveTemplateModal = false;
                this.showTemplatesModal = false;
            } else {
                // Exiting card mode - ensure mic is stopped and state reset
                if (this.isListening) {
                    VoiceInput.stop();
                    this.isListening = false;
                }
                this.cardModeConfirmation = '';
                this.voiceTranscript = '';
                this.voiceFallback = false;
            }
        },

        exitCardMode() {
            this.cardMode = false;
            localStorage.setItem('cardMode', 'false');
            if (this.isListening) {
                VoiceInput.stop();
                this.isListening = false;
            }
            this.cardModeConfirmation = '';
            this.voiceTranscript = '';
            this.voiceFallback = false;
        },

        // Get focus exercise for card mode
        getCardFocusExercise() {
            if (!this.currentWorkout || !this.currentWorkout.exercises || this.currentWorkout.exercises.length === 0) {
                return null;
            }
            // Use focus_exercise from workout, or last exercise
            const focusId = this.currentWorkout.focus_exercise;
            if (focusId) {
                return this.currentWorkout.exercises.find(e => e.exercise_id === focusId);
            }
            return this.currentWorkout.exercises[this.currentWorkout.exercises.length - 1];
        },

        // Get last set for card mode display
        getCardLastSet() {
            const exercise = this.getCardFocusExercise();
            if (!exercise || !exercise.sets || exercise.sets.length === 0) {
                return null;
            }
            return exercise.sets[exercise.sets.length - 1];
        },

        // Get total sets for today
        getCardTotalSets() {
            if (!this.currentWorkout || !this.currentWorkout.exercises) return 0;
            return this.currentWorkout.exercises.reduce((total, ex) => total + (ex.sets?.length || 0), 0);
        },

        // Card mode voice - tap anywhere to start listening
        cardModeTapToSpeak() {
            if (this.isListening) {
                VoiceInput.stop();
                this.isListening = false;
            } else {
                if (VoiceInput.start()) {
                    this.isListening = true;
                    this.voiceTranscript = '';
                    this.voiceFallback = false;
                    this.cardModeConfirmation = '';
                } else {
                    // Inform user when mic is unavailable or permission is blocked
                    this.showCardConfirmation('Mic unavailable. Check permissions or use standard mode.', 'error');
                }
            }
        },

        // Show card mode confirmation
        showCardConfirmation(message, type = 'success') {
            this.cardModeConfirmation = message;
            this.cardModeConfirmationType = type;

            // Auto-clear after delay
            setTimeout(() => {
                this.cardModeConfirmation = '';
            }, 2500);
        },

        // Override voice result handler for card mode
        async handleVoiceResultCardMode(transcript) {
            // Clear any previous fallback UI
            this.voiceFallback = false;
            this.voiceTranscript = '';

            this.isListening = false;
            this.voiceTranscript = transcript;

            try {
                const headers = await API.getHeaders();
                const response = await fetch('/api/voice/process', {
                    method: 'POST',
                    headers,
                    body: JSON.stringify({transcript})
                });

                const result = await response.json();

                if (result.success) {
                    // Check for PR in event result
                    let message = result.message;
                    if (result.event_result?.derived?.is_pr) {
                        message = 'NEW PR! ' + message;
                    }

                    this.showCardConfirmation(message, 'success');

                    if (this.voiceOutputEnabled && VoiceOutput.isSupported()) {
                        VoiceOutput.speak(message);
                    }

                    this.voiceTranscript = '';
                    await this.loadCurrentWorkout();
                } else if (result.fallback) {
                    this.voiceFallback = true;
                    this.showCardConfirmation('Could not process', 'error');

                    if (this.voiceOutputEnabled && VoiceOutput.isSupported()) {
                        VoiceOutput.speak('Could not process');
                    }
                } else {
                    this.showCardConfirmation(result.message, 'error');
                }
            } catch (error) {
                this.showCardConfirmation('Failed to process', 'error');
                this.voiceFallback = true;
            }
        },

        // Get voice hint for current context
        getCardVoiceHint() {
            const exercise = this.getCardFocusExercise();
            if (!exercise) {
                return 'Add an exercise first';
            }
            const lastSet = this.getCardLastSet();
            if (lastSet) {
                // Suggest incrementing or same weight
                return `Say: "${lastSet.weight} for ${lastSet.reps}"`;
            }
            return 'Say: "60kg for 10"';
        }
    };
}
