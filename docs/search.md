# Forgetful Search Functionality

This section details Forgetful's search functionality and associated configuration to allow you to tailor the service to
your use case.

## Auto-Linking Pipeline

When a new memory is created, Forgetful automatically builds knowledge graph connections:

![Memory Auto-Linking Flow](images/Memory%20Autolinking.drawio.png)

**How it works:**

1. **Encode** - The memory's title, content, context, keywords, and tags are combined and converted to a vector embedding
2. **Store** - The embedding is stored in the Forgetful database alongside the memory
3. **Similarity Search** - Existing memories are searched for semantic similarity
4. **Cross-Encoder Reranking** - Candidate matches are scored by the cross-encoder for precision
5. **Auto-Link** - Memories exceeding the 0.7 similarity threshold are automatically linked (bidirectional)

This creates a self-organizing knowledge graph where related concepts connect without manual intervention.

---

## Embedding Providers

### [FastEmbed](https://github.com/qdrant/fastembed)
For local embeddings and re-ranking we support the use of the excellent embedding solution developed by Qdrant. 


### [Google](https://ai.google.dev/gemini-api/docs/embeddings)
We also support Google Embedding models available via the Gemini API

### [Azure](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/tutorials/embeddings?view=foundry-classic&tabs=command-line)
Support for the Azure Foundary OpenAI embeddings is now added as well. 
## Configuration
The following configuration options are available for search