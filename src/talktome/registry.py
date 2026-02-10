from talktome import db

# thin wrapper — delegates to sqlite-backed db module


def register(name, path, metadata=None):
    return db.register(name, path, metadata)


def deregister(name):
    return db.deregister(name)


def get(name):
    return db.get_agent(name)


def list_all():
    return db.list_agents()


def update_status(name, status):
    return db.update_status(name, status)


def update_metadata(name, metadata):
    return db.update_metadata(name, metadata)


def is_registered(name):
    return db.is_registered(name)


def count():
    return db.agent_count()
