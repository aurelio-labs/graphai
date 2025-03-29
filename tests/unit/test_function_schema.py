import inspect

from graphai.utils import FunctionSchema


def scrape_webpage(url: str, name: str = "test") -> str:
    """Provides access to web scraping. You can use this tool to scrape a webpage.
    Many webpages may return no information due to JS or adblock issues, if this
    happens, you must use a different URL.
    """
    return "hello there"


def test_function_schema():
    schema = FunctionSchema.from_callable(scrape_webpage)
    assert schema.name == scrape_webpage.__name__
    assert schema.description == str(inspect.getdoc(scrape_webpage))
    assert schema.signature == str(inspect.signature(scrape_webpage))
    assert schema.output == str(inspect.signature(scrape_webpage).return_annotation)
    assert len(schema.parameters) == 2


def test_function_schema_to_dict():
    schema = FunctionSchema.from_callable(scrape_webpage)
    dict_schema = schema.to_dict()
    assert dict_schema["type"] == "function"
    assert dict_schema["function"]["name"] == schema.name
    assert dict_schema["function"]["description"] == schema.description
    assert dict_schema["function"]["parameters"]["type"] == "object"
    assert (
        dict_schema["function"]["parameters"]["properties"]["url"]["type"] == "string"
    )
    assert (
        dict_schema["function"]["parameters"]["properties"]["name"]["type"] == "string"
    )
    assert (
        dict_schema["function"]["parameters"]["properties"]["url"]["description"]
        is None
    )
    assert (
        dict_schema["function"]["parameters"]["properties"]["name"]["description"]
        is None
    )
    assert dict_schema["function"]["parameters"]["required"] == ["name"]
