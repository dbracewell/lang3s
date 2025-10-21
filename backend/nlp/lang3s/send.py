import inngest

# Create an Inngest client
inngest_client = inngest.Inngest(
    app_id="lang3s-ai",
    api_base_url="http://localhost:8288",
    is_production=False,
)


ids = inngest_client.send_sync(
    inngest.Event(
        name="app/my_function",
        data={"msg": "How now brown cow"},
    )
)
print(f"Event IDs: {ids}")
