import time

# the bridge needs to remember which agents are connected
agents: dict[str, dict] = {}


# register an agent with the bridge
def register(name: str, path: str, metadata: dict | None = None) -> dict:
    entry = {
        "name": name,
        "path": path,
        "status": "active",
        "registered_at": time.time(),
        "last_seen": time.time(),
        "metadata": metadata or {},
    }
    agents[name] = entry
    return entry


# deregister an agent from the bridge
def deregister(name: str) -> bool:
    if name in agents:
        del agents[name]
        return True
    return False


# get an agent's information
def get(name: str) -> dict | None:
    return agents.get(name, None)


# list all registered agents
def list_all() -> list[dict]:
    return list(agents.keys())


# update an agent's status and last seen time
def update_status(name: str, status: str) -> bool:
    if name in agents:
        agents[name]["status"] = status
        agents[name]["last_seen"] = time.time()
        return True
    return False


# update an agent's metadata
def update_metadata(name: str, metadata: dict) -> bool:
    if name in agents:
        agents[name]["metadata"] = metadata
        return True
    return False


# whether an agent is registered
def is_registered(name: str) -> bool:
    return name in agents


# count the number of registered agents
def count() -> int:
    return len(agents)
