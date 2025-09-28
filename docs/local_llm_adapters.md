# Local LLM Adapter Setup

The project ships with adapters for self-hosted inference runtimes so that
adventures can run without relying on cloud APIs. This guide describes the
available adapters, how to configure them, and the options surfaced through the
CLI/provider registry.

## Hugging Face Text Generation Inference (TGI)

The :class:`~textadventure.llm_providers.local.TextGenerationInferenceClient`
communicates with a running TGI server over HTTP.

1. Start a TGI server locally, for example:

   ```bash
   text-generation-launcher --model-id mistralai/Mistral-7B-Instruct-v0.2 \
       --port 8080
   ```

2. Select the provider via the CLI:

   ```bash
   python src/main.py --llm-provider tgi --llm-option base_url=http://localhost:8080 \
       --llm-option default_parameters.max_new_tokens=256
   ```

   The provider registry exposes both `tgi` and the explicit
   `text-generation-inference` aliases. Options prefixed with
   `default_parameters.` are nested under the JSON payload's `parameters`
   object. All other options are passed directly to the adapter constructor.

3. Optional keyword arguments:

   | Option                 | Description                                                        |
   | ---------------------- | ------------------------------------------------------------------ |
   | `generate_path`        | Override the path appended to the base URL (defaults to `/generate`). |
   | `headers`              | Additional HTTP headers to send with each request.                 |
   | `timeout`              | Request timeout in seconds (defaults to the transport default).    |

   Temperature overrides from the coordinator are injected automatically per
   request. The adapter parses usage statistics from the TGI `details.tokens`
   payload when available.

## llama.cpp Python bindings

The :class:`~textadventure.llm_providers.local.LlamaCppClient` wraps the
`llama-cpp-python` package. The adapter can either construct its own
`llama_cpp.Llama` instance or accept a pre-configured client.

### Constructing the client automatically

Provide the `model_path` alongside any keyword arguments that should be passed
to the `Llama` constructor:

```bash
python src/main.py --llm-provider llama-cpp \
    --llm-option model_path=/models/mistral.gguf \
    --llm-option n_ctx=4096
```

The adapter requires the `llama-cpp-python` package to be installed in the
environment. Refer to the upstream documentation for GPU/CPU specific build
instructions.

### Supplying a pre-configured client

If you need to customise initialisation beyond CLI options, dynamically import
a factory that returns an `LLMClient` via the provider registry:

```bash
python src/main.py --llm-provider my_module:create_llama_client
```

Your factory can instantiate `LlamaCppClient(client=existing_llama)` with a
pre-configured `llama_cpp.Llama` instance. When a client object is provided the
adapter disallows additional constructor options to avoid ambiguity.

### Request options

Runtime options such as `n_predict`, `top_p`, and other sampling parameters can
be supplied through `--llm-option` flags. Temperature overrides are applied per
request just like the remote providers.

## Using the adapters programmatically

Import and instantiate the adapters directly when integrating outside of the
CLI:

```python
from textadventure.llm_providers.local import (
    LlamaCppClient,
    TextGenerationInferenceClient,
)

tgi_client = TextGenerationInferenceClient(base_url="http://localhost:8080")
llama_client = LlamaCppClient(model_path="/models/mistral.gguf")
```

Both adapters expose the standard :class:`~textadventure.llm.LLMClient`
interface used throughout the project.
