Most LLM providers accept "function schemas" — a JSON description of a function's name, what it does, and what arguments it takes. Writing those by hand is tedious and easy to get wrong. `FunctionSchema` generates them from your Python functions.

## What it extracts

Given a function, `FunctionSchema` pulls out:

- Its name.
- Its description, from the docstring.
- Its signature and return type.
- Each parameter: type, default, and whether it's required.

## Basic usage

```python
from graphai.utils import FunctionSchema

def scrape_webpage(url: str, name: str = "test") -> str:
    """Provides access to web scraping. You can use this tool to scrape a webpage.
    Many webpages may return no information due to JS or adblock issues, if this
    happens, you must use a different URL.
    """
    return "hello there"

schema = FunctionSchema.from_callable(scrape_webpage)
schema_dict = schema.to_dict()
```

## The output

`to_dict()` produces the common shape most providers accept:

```python
{
    "type": "function",
    "function": {
        "name": "function_name",
        "description": "function_description",
        "parameters": {
            "type": "object",
            "properties": {
                "param_name": {
                    "description": "param_description",
                    "type": "param_type"
                }
            },
            "required": ["required_param1", "required_param2"]
        }
    }
}
```

For OpenAI specifically, `to_openai()` targets either the Chat Completions or the Responses API:

```python
from graphai.utils import OpenAIAPI

schema.to_openai()                          # Chat Completions (the default)
schema.to_openai(api=OpenAIAPI.RESPONSES)   # Responses API
```

## Type mapping

Python types become JSON schema types:

- `int`, `float` → `number`
- `str` → `string`
- `bool` → `boolean`
- anything else → `object`

## Several functions at once

`get_schemas` builds a list of schemas in one call:

```python
from graphai.utils import get_schemas

def function1(x: int) -> str:
    """First function"""
    return str(x)

def function2(y: str, z: bool = False) -> int:
    """Second function"""
    return len(y)

schemas = get_schemas([function1, function2])
```

## From a Pydantic model

Schemas can come from Pydantic models too. Field types, descriptions, and defaults all carry over:

```python
from pydantic import BaseModel
from graphai.utils import FunctionSchema

class SearchQuery(BaseModel):
    """A search query model"""
    query: str
    max_results: int = 10

schema = FunctionSchema.from_pydantic(SearchQuery)
```

## Getting good schemas

1. **Write docstrings.** They become the description the LLM reads to decide when to call your function.
2. **Add type hints** on every parameter and the return value, so types map correctly.
3. **Use defaults** for optional parameters. A parameter with no default is marked required.

The output works with OpenAI, LiteLLM, Ollama, and any other provider that uses the standard function-calling format.
