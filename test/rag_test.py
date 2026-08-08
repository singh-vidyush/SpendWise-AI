from knowledge_ingestion import knowledge_collection, embedding_model


query = "How should I plan SIP investment?"


query_embedding = embedding_model.embed_query(
    query
)


result = knowledge_collection.query(
    query_embeddings=[
        query_embedding
    ],
    n_results=3
)


print("\nRetrieved Documents:\n")

for doc in result["documents"][0]:
    print("----------------------")
    print(doc[:500])