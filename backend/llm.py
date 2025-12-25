"""LLM integration for voice command processing."""
import os
import json
from typing import Dict, Any, List, Optional

from backend.config import (
    USE_OPENAI,
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
    LLM_MODEL,
    LLM_MAX_TOKENS
)
from backend.database import get_projection, get_exercises

# Initialize LLM client based on configuration
if USE_OPENAI:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
    client_type = "openai"
else:
    from anthropic import Anthropic
    client = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
    client_type = "anthropic"

SYSTEM_PROMPT = """You are a voice assistant for a gym workout tracker. Users speak commands to log their strength training exercises.

## Current Context
- Active workout: {workout_status}
- Workout ID: {workout_id}
- Focus exercise: {focus_exercise}
- Exercises in workout: {exercise_list}
- Previous session (focus exercise): {previous_values}
- User's preferred unit: {preferred_unit}

## Available Exercises in Library
{available_exercises}

**IMPORTANT:** When the user mentions an exercise, you MUST map it to an exercise ID from the library above. Use fuzzy matching:
- "bench" → "bench-press"
- "pull ups" or "pullups" → "pull-up"
- "lat pulldown" → "lat-pulldown"
- "BP" → "bench-press"
- "OHP" → "overhead-press"

If the user says an exercise not in the library, ask for clarification or suggest the closest match.

## Available Tools
1. emit(event_type, payload) - Create a workout event
2. query(projection_key) - Get current state

## Event Types
- WorkoutStarted: Start a new workout
- SetLogged: Log a set (requires exercise_id, weight, reps, unit)
- ExerciseAdded: Add exercise without logging a set
- WorkoutCompleted: Finish the workout

## Guidelines
1. For logging sets: emit SetLogged with workout_id (from context), exercise_id, weight, reps, unit
2. **ALWAYS use exact exercise_id from Available Exercises list above**
3. If user doesn't name exercise, use focus_exercise
4. For "same as last time" or "same weight": Use the Previous session values above
5. For "add 5 pounds" or "plus 5": Add to the previous weight (convert: 5 lbs = 2.27 kg)
6. Always include workout_id in SetLogged events - get it from Active workout context

## Response Style
- Be extremely concise. Your responses are read aloud via text-to-speech.
- NEVER mention technical details like "exercise ID", "library", "database", "emit", "payload", etc.
- Just confirm the action naturally, like a gym buddy would.
- Good: "Got it, 100kg for 8 reps on bench press."
- Good: "Logged barbell row, 80kg, 10 reps."
- Good: "Workout complete! Nice session."
- Bad: "I'll use the bench-press exercise ID from our library."
- Bad: "Emitting a SetLogged event with the payload..."

## Examples
- "Bench press 100 for 8" → emit SetLogged, respond: "Got it, bench press 100 for 8."
- "100 for 8" (with focus) → emit SetLogged, respond: "Logged 100 for 8."
- "Same as last time" → Use previous_values, emit SetLogged, respond: "Same as last time, got it."
- "Add 5 pounds" → Add 2.27kg to previous weight, emit SetLogged
- "I'm done" → emit WorkoutCompleted, respond: "Workout complete!"
"""

# Define tools based on client type
if client_type == "openai":
    TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "emit",
                "description": "Emit a workout event",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "event_type": {
                            "type": "string",
                            "enum": ["WorkoutStarted", "SetLogged", "ExerciseAdded", "WorkoutCompleted", "WorkoutDiscarded"]
                        },
                        "payload": {
                            "type": "object",
                            "description": "Event payload"
                        }
                    },
                    "required": ["event_type", "payload"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "query",
                "description": "Query a projection for current state",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "projection_key": {
                            "type": "string",
                            "description": "Projection key like 'current_workout' or 'exercise_history:bench-press'"
                        }
                    },
                    "required": ["projection_key"]
                }
            }
        }
    ]
else:  # anthropic
    TOOLS = [
        {
            "name": "emit",
            "description": "Emit a workout event",
            "input_schema": {
                "type": "object",
                "properties": {
                    "event_type": {
                        "type": "string",
                        "enum": ["WorkoutStarted", "SetLogged", "ExerciseAdded", "WorkoutCompleted", "WorkoutDiscarded"],
                        "description": "Type of event to emit"
                    },
                    "payload": {
                        "type": "object",
                        "description": "Event payload"
                    }
                },
                "required": ["event_type", "payload"]
            }
        },
        {
            "name": "query",
            "description": "Query a projection for current state",
            "input_schema": {
                "type": "object",
                "properties": {
                    "projection_key": {
                        "type": "string",
                        "description": "Projection key like 'current_workout' or 'exercise_history:bench-press'"
                    }
                },
                "required": ["projection_key"]
            }
        }
    ]

def build_context(user_id: str = "default") -> Dict[str, str]:
    """Build context for the LLM prompt."""
    current = get_projection("current_workout", user_id)
    exercises = get_exercises(user_id)

    # Format exercise library for LLM
    if exercises:
        exercise_library = "\n".join([
            f"- {ex['id']}: {ex['name']}"
            for ex in exercises
        ])
    else:
        exercise_library = "No exercises in library yet."

    if current:
        workout_status = f"Active (ID: {current['id'][:8]})"
        workout_id = current['id']
        focus = current.get("focus_exercise", "None")
        ex_list = ", ".join(e["exercise_id"] for e in current.get("exercises", []))

        # Get previous session for focus exercise (for "same as last time")
        previous_values = "None"
        if focus and focus != "None":
            history = get_projection(f"exercise_history:{focus}", user_id)
            if history and history.get("sessions"):
                last_session = history["sessions"][0]
                if last_session.get("sets"):
                    last_set = last_session["sets"][0]
                    previous_values = f"{last_set.get('weight', 0)}{last_set.get('unit', 'kg')} x {last_set.get('reps', 0)}"
    else:
        workout_status = "None"
        workout_id = "None"
        focus = "None"
        ex_list = "None"
        previous_values = "None"

    return {
        "workout_status": workout_status,
        "workout_id": workout_id,
        "focus_exercise": focus,
        "exercise_list": ex_list or "None",
        "available_exercises": exercise_library,
        "previous_values": previous_values,
        "preferred_unit": "kg"  # TODO: Get from user settings
    }

PLAN_BUILDER_PROMPT = """You are a voice assistant for planning gym workout templates. Users speak commands to build workout templates with exercises and target values.

## Available Exercises in Library
{available_exercises}

**IMPORTANT:** When the user mentions an exercise, you MUST map it to an exercise ID from the library above. Use fuzzy matching:
- "bench" → "bench-press"
- "pull ups" or "pullups" → "pull-up"
- "lat pulldown" → "lat-pulldown"
- "BP" → "bench-press"
- "OHP" → "overhead-press"

## Available Tools
1. emit(event_type, payload) - Add an exercise to the template

## Event Types for Template Building
- ExerciseAdded: Add exercise with target sets/reps/weight
  - payload: {{ exercise_id, target_sets, target_reps, weight (optional), unit }}

## Guidelines
1. When user says "add bench press, 4 sets of 8 at 100kg":
   - emit ExerciseAdded with exercise_id="bench-press", target_sets=4, target_reps=8, weight=100, unit="kg"
2. When user says "add squats 5x5":
   - emit ExerciseAdded with exercise_id="squat", target_sets=5, target_reps=5
3. When user says "remove bench" or "delete bench press":
   - Just respond with text (frontend will handle removal)

## Response Style
- Be extremely concise. Your responses are read aloud.
- Never mention technical details like "exercise ID", "library", "emit", etc.
- Good: "Added bench press, 4 sets of 8 at 100kg"
- Good: "Adding squats, 5 by 5"
"""


def process_voice_command(
    transcript: str,
    user_id: str = "default",
    mode: str = None
) -> Dict[str, Any]:
    """Process a voice command transcript using LLM."""
    if not client:
        api_type = "OPENAI_API_KEY" if USE_OPENAI else "ANTHROPIC_API_KEY"
        return {
            "success": False,
            "error": f"LLM not configured. Set {api_type}.",
            "fallback": True,
            "transcript": transcript
        }

    context = build_context(user_id)

    # Use different prompt for plan builder mode
    if mode == "plan_builder":
        prompt = PLAN_BUILDER_PROMPT.format(available_exercises=context["available_exercises"])
    else:
        prompt = SYSTEM_PROMPT.format(**context)

    try:
        if client_type == "openai":
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": transcript}
                ],
                tools=TOOLS,
                tool_choice="auto",
                max_tokens=LLM_MAX_TOKENS
            )

            message = response.choices[0].message

            # Check for tool calls
            if message.tool_calls:
                tool_call = message.tool_calls[0]
                function_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)

                return {
                    "success": True,
                    "action": function_name,
                    "arguments": arguments,
                    "message": message.content or ""
                }
            else:
                # No tool call, just a message
                return {
                    "success": True,
                    "action": None,
                    "message": message.content or "I didn't understand that command."
                }
        else:  # anthropic
            response = client.messages.create(
                model=LLM_MODEL,
                max_tokens=LLM_MAX_TOKENS,
                system=prompt,
                messages=[
                    {"role": "user", "content": transcript}
                ],
                tools=TOOLS
            )

            # Check for tool use
            if response.stop_reason == "tool_use":
                tool_use = next(block for block in response.content if block.type == "tool_use")
                function_name = tool_use.name
                arguments = tool_use.input

                return {
                    "success": True,
                    "action": function_name,
                    "arguments": arguments,
                    "message": ""
                }
            else:
                # No tool use, just a message
                text_content = next((block.text for block in response.content if block.type == "text"), "I didn't understand that command.")
                return {
                    "success": True,
                    "action": None,
                    "message": text_content
                }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "fallback": True,
            "transcript": transcript
        }
