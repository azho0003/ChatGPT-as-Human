import tiktoken
import openai
import json
import time

from prompt import get_prompt

USE_GPT_4 = True
GPT_35_MAX_TOKENS = 4097
GPT_4_MAX_TOKENS = 8192
OUTPUT_TOKENS = 300


def num_tokens_from_messages(messages, model="gpt-3.5-turbo-0613"):
    """Return the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    if model in {
        "gpt-3.5-turbo-0613",
        "gpt-3.5-turbo-16k-0613",
        "gpt-4-0314",
        "gpt-4-32k-0314",
        "gpt-4-0613",
        "gpt-4-32k-0613",
    }:
        tokens_per_message = 3
        tokens_per_name = 1
    elif model == "gpt-3.5-turbo-0301":
        tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif "gpt-3.5-turbo" in model:
        print("Warning: gpt-3.5-turbo may update over time. Returning num tokens assuming gpt-3.5-turbo-0613.")
        return num_tokens_from_messages(messages, model="gpt-3.5-turbo-0613")
    elif "gpt-4" in model:
        print("Warning: gpt-4 may update over time. Returning num tokens assuming gpt-4-0613.")
        return num_tokens_from_messages(messages, model="gpt-4-0613")
    else:
        raise NotImplementedError(
            f"""num_tokens_from_messages() is not implemented for model {model}. See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens."""
        )
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens


def get_model(messages):
    if USE_GPT_4:
        tokens = num_tokens_from_messages(messages)
        if tokens < GPT_4_MAX_TOKENS - OUTPUT_TOKENS:
            model = "gpt-4"
        else:
            print("Using 32k model")
            model = "gpt-4-32k"
    else:
        tokens = num_tokens_from_messages(messages)
        if tokens < GPT_35_MAX_TOKENS - OUTPUT_TOKENS:
            model = "gpt-3.5-turbo"
        else:
            print("Using 16k model")
            model = "gpt-3.5-turbo-16k"

    return model


def ask_gpt(history, view, task, persona):
    role = get_prompt("role")
    template = get_prompt("template")

    formatted_history = "\n".join(json.dumps(h) for h in history) if len(history) > 0 else "None"

    if "scroll-reference" not in view:
        print("Removing scroll action")
        role_template = "\n".join(line for line in role.split("\n") if "scroll" not in line)
    else:
        role_template = role

    messages = [
        {"role": "system", "content": role_template.format(persona["name"], persona["age"])},
        {"role": "user", "content": template.format(task, formatted_history, view)},
    ]
    print(messages)

    model = get_model(messages)

    print("Getting ChatGPT response")

    # Ask the model to generate three actions
    responses = get_chat_completion(model=model, messages=messages, n=3)

    # Pass the responses along with the context for further evaluation
    return get_best_action(responses, task, persona)


def get_best_action(responses, task, persona):
    actions = [choice["message"]["content"] for choice in responses["choices"]]
    formatted_actions = "\n".join(actions)

    role = get_prompt("get_best_role")
    template = get_prompt("get_best_template")
    messages = [
        {"role": "system", "content": role.format(persona["name"], persona["age"])},
        {"role": "user", "content": template.format(task, formatted_actions)},
    ]

    model = get_model(messages)
    return get_chat_completion(model=model, messages=messages)


def get_chat_completion(**kwargs):
    while True:
        try:
            return openai.ChatCompletion.create(**kwargs)
        except (openai.error.RateLimitError, openai.error.ServiceUnavailableError) as e:
            print(e)
            # Waiting 1 minute as that is how long it takes the rate limit to reset
            print("Rate limit reached, waiting 1 minute")
            time.sleep(60)
