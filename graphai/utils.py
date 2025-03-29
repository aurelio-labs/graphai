import inspect
from typing import Any, Callable, List, Optional
from pydantic import BaseModel, Field
from semantic_router.utils.logger import logger


class Parameter(BaseModel):
    """Parameter for a function.

    :param name: The name of the parameter.
    :type name: str
    :param description: The description of the parameter.
    :type description: Optional[str]
    :param type: The type of the parameter.
    :type type: str
    :param default: The default value of the parameter.
    :type default: Any
    :param required: Whether the parameter is required.
    :type required: bool
    """

    name: str = Field(description="The name of the parameter")
    description: Optional[str] = Field(
        default=None, description="The description of the parameter"
    )
    type: str = Field(description="The type of the parameter")
    default: Any = Field(description="The default value of the parameter")
    required: bool = Field(description="Whether the parameter is required")

    def to_dict(self) -> dict[str, Any]:
        """Convert the parameter to a dictionary for an standard dictionary-based function schema.
        This is the most common format used by LLM providers, including OpenAI, Ollama, and others.

        :return: The parameter in dictionary format.
        :rtype: dict[str, Any]
        """
        return {
            self.name: {
                "description": self.description,
                "type": self.type,
            }
        } 

class FunctionSchema(BaseModel):
    """Class that consumes a function and can return a schema required by
    different LLMs for function calling.
    """
    name: str = Field(description="The name of the function")
    description: str = Field(description="The description of the function")
    signature: str = Field(description="The signature of the function")
    output: str = Field(description="The output of the function")
    parameters: list[Parameter] = Field(description="The parameters of the function")

    def __init__(
        self,
        name: str,
        description: str,
        signature: str,
        output: str,
        parameters: list[Parameter]
    ):
        self.name = name
        self.description = description
        self.signature = signature
        self.output = output
        self.parameters = parameters
        
        
    @classmethod
    def from_callable(cls, function: Callable) -> "FunctionSchema":
        """Initialize the FunctionSchema.

        :param function: The function to consume.
        :type function: Callable
        """
        if callable(function):
            name = function.__name__
            description = str(inspect.getdoc(function))
            if description is None or description == "":
                logger.warning(f"Function {name} has no docstring")
            signature = str(inspect.signature(function))
            output = str(inspect.signature(function).return_annotation)
            parameters = []
            for param in inspect.signature(function).parameters.values():
                parameters.append(
                    Parameter(
                        name=param.name,
                        type=param.annotation.__name__,
                        default=param.default,
                        required=param.default is inspect.Parameter.empty,
                    )
                )
            return cls(
                name=name,
                description=description,
                signature=signature,
                output=output,
                parameters=parameters,
            )
        elif isinstance(function, BaseModel):
            raise NotImplementedError("Pydantic BaseModel not implemented yet.")
        else:
            raise TypeError("Function must be a Callable or BaseModel")
    
    @classmethod
    def from_pydantic(cls, model: BaseModel) -> "FunctionSchema":
        signature_parts = []
        for field_name, field_model in model.__annotations__.items():
            field_info = model.model_fields[field_name]
            default_value = field_info.default
            if default_value:
                default_repr = repr(default_value)
                signature_part = (
                    f"{field_name}: {field_model.__name__} = {default_repr}"
                )
            else:
                signature_part = f"{field_name}: {field_model.__name__}"
            signature_parts.append(signature_part)
        signature = f"({', '.join(signature_parts)}) -> str"
        return cls(
            name=model.__class__.__name__,
            description=model.__doc__ or "",
            signature=signature,
            output="",  # TODO: Implement output
            parameters=[],
        )
        
    def _process_function(self, function: Callable):
        self.name = function.__name__
        self.description = str(inspect.getdoc(function))
        if self.description is None or self.description == "":
            logger.warning(f"Function {self.name} has no docstring")
        self.signature = str(inspect.signature(function))
        self.output = str(inspect.signature(function).return_annotation)
        parameters = []
        for param in inspect.signature(function).parameters.values():
            parameters.append(
                Parameter(
                    name=param.name,
                    type=param.annotation.__name__,
                    default=param.default,
                    required=param.default is inspect.Parameter.empty,
                )
            )
        self.parameters = parameters

    def to_dict(self) -> dict:
        schema_dict = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        param.to_dict() for param in self.parameters
                    },
                    "required": [
                        param.name for param in self.parameters if param.required
                    ],
                },
            },
        }
        return schema_dict

    def to_openai(self) -> dict:
        return self.to_dict()

    def _openai_type_mapping(self, param_type: str) -> str:
        if param_type == "int":
            return "number"
        elif param_type == "float":
            return "number"
        elif param_type == "str":
            return "string"
        elif param_type == "bool":
            return "boolean"
        else:
            return "object"

DEFAULT = set(["default", "openai", "ollama", "litellm"])

def get_schemas(callables: List[Callable], format: str = "default") -> list[dict]:
    if format in DEFAULT:
        return [FunctionSchema(callable).to_dict() for callable in callables]
    else:
        raise ValueError(f"Format {format} not supported")
