#!/usr/bin/env python3

import os
import sys
import json
import time
import subprocess
import argparse
import logging
from tqdm import tqdm
from pynput import keyboard

# Set up logging
logging.basicConfig(
    filename='script.log',
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s:%(message)s'
)

paused = False

def on_press(key):
    global paused
    try:
        if key == keyboard.Key.f6:
            paused = not paused
            state = "Paused" if paused else "Resumed"
            print(f"\n{state}... (Press F6 to {('resume' if paused else 'pause')})")
            logging.info(f"Process {state.lower()} by user.")
    except AttributeError:
        pass

def start_keyboard_listener():
    print("\nPress F6 at any time to pause/resume processing")
    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    return listener

def edit_character(character):
    print("\nCurrent character details:")
    for key, value in character.items():
        print(f"{key}: {value}")
    
    print("\nEdit character details (press Enter to keep current value):")
    for key in character:
        new_value = input(f"New {key}: ").strip()
        if new_value:
            character[key] = new_value
    return character

def load_voiceover(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logging.error(f"Error reading voiceover file {file_path}: {e}")
        return ""

def run_ollama(prompt):
    try:
        command = ["ollama", "run", "mistral-nemo"]
        result = subprocess.run(
            command,
            input=prompt,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        if result.returncode != 0:
            logging.error(f"Ollama error: {result.stderr}")
            return ""
        logging.debug(f"LLM Response:\n{result.stdout.strip()}")
        return result.stdout.strip()
    except Exception as e:
        logging.error(f"Error running Ollama: {e}")
        return ""

def parse_json_response_characters(response):
    try:
        start = response.find('[')
        end = response.rfind(']') + 1
        
        if start == -1 or end == 0:
            logging.error("No JSON array found in character response")
            return []
            
        json_str = response[start:end]
        json_str = json_str.strip().rstrip('\\')
        parsed = json.loads(json_str)
        
        if not isinstance(parsed, list):
            logging.error("Parsed character JSON is not an array")
            return []
            
        characters = []
        for char in parsed:
            if isinstance(char, dict):
                normalized = {
                    'name': char.get('Name', char.get('name', 'Unknown')),
                    'age': char.get('Age', char.get('age', 'Unknown')),
                    'description': char.get('Description', char.get('description', '')),
                    'clothing': char.get('Clothing', char.get('clothing', '')),
                    'role': char.get('Role', char.get('role', ''))
                }
                characters.append(normalized)
        
        if characters:
            logging.info(f"Successfully parsed {len(characters)} characters")
            return characters
        else:
            logging.warning("No valid character data found in JSON")
            return []
            
    except json.JSONDecodeError as e:
        logging.error(f"JSON parsing error (characters): {e}")
        logging.debug(f"Attempted to parse: {json_str}")
        return []
    except Exception as e:
        logging.error(f"Unexpected error during character parsing: {e}")
        logging.debug(f"Raw response:\n{response}")
        return []

def parse_json_response_scenes(response):
    try:
        start = response.find('[')
        end = response.rfind(']') + 1
        
        if start == -1 or end == 0:
            logging.error("No JSON array found in scene response")
            return []
            
        json_str = response[start:end]
        parsed = json.loads(json_str)
        
        if not isinstance(parsed, list):
            logging.error("Parsed scene JSON is not an array")
            return []
            
        scenes = []
        for scene in parsed:
            if isinstance(scene, dict):
                normalized = {
                    'Scene': scene.get('Scene', 'Unknown'),
                    'Voiceover': scene.get('Voiceover', ''),
                    'Description': scene.get('Description', '')
                }
                scenes.append(normalized)
        
        if scenes:
            logging.info(f"Successfully parsed {len(scenes)} scenes")
            return scenes
        else:
            logging.warning("No valid scene data found in JSON")
            return []
            
    except json.JSONDecodeError as e:
        logging.error(f"JSON parsing error (scenes): {e}")
        logging.debug(f"Attempted to parse: {json_str}")
        return []
    except Exception as e:
        logging.error(f"Unexpected error during scene parsing: {e}")
        logging.debug(f"Raw response:\n{response}")
        return []

def identify_characters(voiceover_text, num_characters):
    prompt = f"""
You are a visual storyteller creating character descriptions.

Instructions:
- Analyze the voiceover text and identify {num_characters} key characters.
- Create detailed but concise visual descriptions for each character.
- Ensure each description is clear enough to maintain consistency across scenes.

For each character, provide:
- "Name": Full name
- "Age": Specific age
- "Description": Clear physical description
- "Clothing": Specific clothing details
- "Role": Their function in the story

Format as JSON array with {num_characters} character objects.

Voiceover Text:
{voiceover_text}
"""
    logging.debug(f"Identify Characters Prompt:\n{prompt}")
    response = run_ollama(prompt)
    logging.debug(f"Identify Characters Response:\n{response}")
    characters = parse_json_response_characters(response)
    if characters is None:
        characters = []
    return characters

def generate_negative_prompt():
    negative_prompt = "Cartoonish features, supernatural elements, exaggerated expressions, bright colors, unrealistic poses, inconsistent lighting, text, blurry details, distorted proportions"
    logging.info(f"Using negative prompt: {negative_prompt}")
    return negative_prompt

def generate_character_prompts(characters, negative_prompt):
    prompts = []
    for character in characters:
        first_name = character['name'].split()[0] if character['name'] != 'Unknown' else 'Character'
        description = character['description'].rstrip('.')
        clothing = character['clothing'].rstrip('.')
        
        positive_prompt = (
            f"{character['name']}, {character['age']} years old, {description}, wearing {clothing}. "
            "Comic book-style illustration with a dark, gritty, realistic vibe."
        )
        prompt_data = {
            "Name": character['name'],
            "Positive prompt": positive_prompt,
            "Negative prompt": negative_prompt
        }
        prompts.append(prompt_data)
    return prompts

def suggest_scenes(voiceover_text, num_scenes):
    prompt = f"""
You are a visual storyteller specializing in psychological narratives.

Create {num_scenes} powerful visual scenes that:
- Show psychological states, behaviors, or social phenomena
- Can include both individual experiences or group dynamics
- Build tension and progression in the story
- Focus on visually striking moments
- Avoid graphic content while maintaining impact

For each scene provide:
- "Scene": Brief identifier
- "Voiceover": Key narrative line
- "Description": Clear visual description focusing on:
  * Key actions or states
  * Environmental details that reflect mental states
  * Character expressions and body language
  * Group dynamics when relevant
  * Atmospheric elements

Format as JSON array with {num_scenes} scene objects.

Voiceover Text:
{voiceover_text}
"""
    logging.debug(f"Suggest Scenes Prompt:\n{prompt}")
    response = run_ollama(prompt)
    logging.debug(f"Suggest Scenes Response:\n{response}")
    scenes = parse_json_response_scenes(response)
    if scenes is None:
        scenes = []
    return scenes

def generate_scene_prompts(scenes, characters, negative_prompt):
    prompts = []
    for scene in tqdm(scenes, desc="Generating scene prompts"):
        while paused:
            time.sleep(0.1)
                
        llm_prompt = f"""
You are a visual storyteller creating prompts for psychological narratives.

Create a clear, impactful scene description that:
1. Starts with the main visual element/action
2. Includes relevant character details when needed:
   - Main characters: [name], [age], [appearance], [clothing], [action/state]
   - Group dynamics: Clear but brief descriptions of crowd behavior
3. Adds environmental details that reflect psychological states
4. Keeps descriptions concise but powerful
5. Avoids dialogue or text
6. Uses visual metaphors Stable Diffusion can create

Scene Information:
- Scene: {scene['Scene']}
- Voiceover: {scene['Voiceover']}
- Description: {scene['Description']}

Available Characters:
{json.dumps(characters, indent=2)}

Create a JSON object with:
- "Name": Scene identifier
- "Positive prompt": Brief, powerful scene description. MUST end with "Comic book-style illustration with a dark, gritty, realistic vibe."
- "Negative prompt": "{negative_prompt}"

Format as single JSON object.
"""
        logging.debug(f"Generate Scene Prompt for {scene['Scene']}:\n{llm_prompt}")
        response = run_ollama(llm_prompt)
        logging.debug(f"Generate Scene Response for {scene['Scene']}:\n{response}")
        scene_prompt = parse_json_response_scene_prompts(response)
        if scene_prompt:
            if 'positive prompt' in scene_prompt:
                positive_prompt = scene_prompt.get("positive prompt", "")
                if "Comic book-style illustration" not in positive_prompt:
                    positive_prompt += " Comic book-style illustration with a dark, gritty, realistic vibe."
                prompts.append({
                    "Name": scene_prompt.get("name", scene['Scene']),
                    "Positive prompt": positive_prompt,
                    "Negative prompt": negative_prompt
                })
            else:
                logging.error(f"Missing keys in scene prompt for scene: {scene['Scene']}")
        else:
            logging.error(f"Failed to generate prompt for scene: {scene['Scene']}")
    return prompts

def parse_json_response_scene_prompts(response):
    try:
        response = response.strip('`').strip()
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        
        if json_start == -1 or json_end == 0:
            logging.error("No JSON object found in scene prompt response")
            return {}
        
        json_str = response[json_start:json_end]
        parsed = json.loads(json_str)
        
        if isinstance(parsed, dict):
            parsed_normalized = {k.lower(): v for k, v in parsed.items()}
            if all(k in parsed_normalized for k in ["name", "positive prompt", "negative prompt"]):
                return parsed_normalized
            else:
                logging.error("Parsed scene prompt JSON is missing required keys")
                return {}
        else:
            logging.error("Parsed scene prompt JSON is not an object")
            return {}
            
    except json.JSONDecodeError as e:
        logging.error(f"JSON parsing error (scene prompts): {e}")
        logging.debug(f"Attempted to parse: {json_str}")
        return {}
    except Exception as e:
        logging.error(f"Unexpected error during scene prompt parsing: {e}")
        logging.debug(f"Raw response:\n{response}")
        return {}

def save_prompts(prompts, file_path):
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding="utf-8") as f:
            for prompt in prompts:
                if isinstance(prompt, dict):
                    name = prompt.get('Name', prompt.get('name', 'Unknown'))
                    positive_prompt = prompt.get('Positive prompt', prompt.get('positive prompt', ''))
                    negative_prompt = prompt.get('Negative prompt', prompt.get('negative prompt', ''))
                    f.write(f"Name: {name}\nPositive prompt: {positive_prompt}\nNegative prompt: {negative_prompt}\n---\n")
                else:
                    f.write(f"{prompt}\n")
        print(f"Prompts saved to {file_path}")
        logging.info(f"Prompts saved to {file_path}")
    except Exception as e:
        logging.error(f"Error saving prompts to {file_path}: {e}")

def main():
    parser = argparse.ArgumentParser(description='Visual Storytelling Prompt Generation Tool')
    parser.add_argument('--auto', action='store_true', help='Run in automatic mode')
    args = parser.parse_args()

    listener = start_keyboard_listener()

    input_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'input')
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')

    try:
        os.makedirs(output_dir, exist_ok=True)
    except Exception as e:
        logging.error(f"Error creating output directory {output_dir}: {e}")
        print(f"Failed to create output directory: {output_dir}")
        sys.exit(1)

    stories = [f for f in os.listdir(input_dir) if f.endswith('.txt')]

    if not stories:
        print("No voiceover files found in the input directory.")
        logging.error("No voiceover files found in the input directory.")
        sys.exit(1)

    enable_editing = input("Would you like to enable character editing features? (yes/no): ").strip().lower() == 'yes'

    if not args.auto and not enable_editing:
        mode = input("Do you want to run in automatic mode? (yes/no): ").strip().lower()
        if mode == 'yes':
            args.auto = True

    if args.auto:
        num_characters_input = input("\nEnter the average number of main characters per story: ").strip()
        if not num_characters_input.isdigit():
            print("Please enter a valid number.")
            sys.exit(1)
        num_characters = int(num_characters_input)

        num_scenes_input = input("\nEnter the average number of scenes per story: ").strip()
        if not num_scenes_input.isdigit():
            print("Please enter a valid number.")
            sys.exit(1)
        num_scenes = int(num_scenes_input)
    else:
        num_characters = None
        num_scenes = None

    for story_file in stories:
        story_name = os.path.splitext(story_file)[0]
        story_output_dir = os.path.join(output_dir, story_name)

        try:
            os.makedirs(story_output_dir, exist_ok=True)
        except Exception as e:
            logging.error(f"Error creating story output directory {story_output_dir}: {e}")
            print(f"Failed to create story output directory: {story_output_dir}")
            continue

        voiceover_text = load_voiceover(os.path.join(input_dir, story_file))

        print(f"\nProcessing story: {story_name}")
        logging.info(f"Processing story: {story_name}")

        if not args.auto:
            num_characters_input = input("\nEnter the number of main characters you want for this story: ").strip()
            if not num_characters_input.isdigit():
                print("Please enter a valid number.")
                continue
            num_characters = int(num_characters_input)

        characters = identify_characters(voiceover_text, num_characters)

        if not characters:
            print("No characters identified.")
            logging.warning("No characters identified.")
            continue

        if not args.auto:
            print("\nIdentified Characters:")
            for idx, char in enumerate(characters):
                print(f"{idx + 1}. {char['name']} (Age: {char['age']}, Role: {char['role']})")
                print(f"   Description: {char['description']}")
                print(f"   Clothing: {char['clothing']}")

            if enable_editing:
                edit_choice = input("\nWould you like to edit any characters? (yes/no): ").strip().lower()
                if edit_choice == 'yes':
                    while True:
                        char_num = input("Enter character number to edit (or 'done' to finish): ").strip()
                        if char_num.lower() == 'done':
                            break
                        try:
                            idx = int(char_num) - 1
                            if 0 <= idx < len(characters):
                                characters[idx] = edit_character(characters[idx])
                            else:
                                print("Invalid character number.")
                        except ValueError:
                            print("Please enter a valid number.")

            selected = input("\nEnter the numbers of the characters you want to include (e.g., 1,3): ").strip()
            selected_indices = [int(i)-1 for i in selected.split(',') if i.strip().isdigit()]
            characters = [characters[i] for i in selected_indices if 0 <= i < len(characters)]

        negative_prompt = generate_negative_prompt()

        character_prompts = generate_character_prompts(characters, negative_prompt)
        save_prompts(character_prompts, os.path.join(story_output_dir, f"characters_{story_name}.txt"))

        more_images = True
        total_scenes = []

        while more_images:
            if not args.auto:
                num_scenes_input = input("\nEnter the number of scenes you want to generate: ").strip()
                if not num_scenes_input.isdigit():
                    print("Please enter a valid number.")
                    continue
                num_scenes = int(num_scenes_input)

            scenes = suggest_scenes(voiceover_text, num_scenes)

            if not scenes:
                print("No scenes generated.")
                logging.warning("No scenes generated.")
                break

            if not args.auto:
                print("\nProposed Scenes:")
                for idx, scene in enumerate(scenes):
                    print(f"{idx + 1}. {scene['Voiceover']}")
                    print(f"   Description: {scene['Description']}")
                selected = input("\nEnter the numbers of the scenes you want to include (e.g., 1,3): ").strip()
                selected_indices = [int(i)-1 for i in selected.split(',') if i.strip().isdigit()]
                selected_scenes = [scenes[i] for i in selected_indices if 0 <= i < len(scenes)]
            else:
                selected_scenes = scenes

            scene_prompts = generate_scene_prompts(selected_scenes, characters, negative_prompt)
            if scene_prompts:
                save_prompts(scene_prompts, os.path.join(story_output_dir, f"scenes_{story_name}.txt"))
            else:
                logging.warning("No scene prompts generated.")

            total_scenes.extend(selected_scenes)

            if not args.auto:
                more = input("Do you want to generate more scenes? (yes/no): ").strip().lower()
                if more != 'yes':
                    more_images = False
            else:
                more_images = False  # In auto mode, we do not loop for more scenes

        chosen_images_path = os.path.join(story_output_dir, "chosen_images.txt")
        try:
            with open(chosen_images_path, 'w', encoding="utf-8") as f:
                for scene in total_scenes:
                    f.write(f'Name: {scene["Scene"]}\nVoiceover: "{scene["Voiceover"]}"\n---\n')
            print(f"Chosen images saved to {chosen_images_path}")
            logging.info(f"Chosen images saved to {chosen_images_path}")
        except Exception as e:
            logging.error(f"Error saving chosen images to {chosen_images_path}: {e}")

    # Stop keyboard listener
    listener.stop()

if __name__ == '__main__':
    main()