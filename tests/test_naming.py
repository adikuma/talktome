from talktome.hooks import derive_agent_name


def test_simple_project():
    # project in a non generic parent should use parent prefix
    assert derive_agent_name("/home/user/myapp/backend") == "myapp-backend"


def test_generic_parent_desktop():
    # desktop is generic, skip it and use just the folder name
    assert derive_agent_name("/Users/adity/Desktop/talktome") == "talktome"


def test_generic_parent_projects():
    # projects is generic, skip it
    assert derive_agent_name("/home/user/projects/myapp") == "myapp"


def test_generic_parent_repos():
    # repos is generic, skip it
    assert derive_agent_name("/home/user/repos/frontend") == "frontend"


def test_generic_parent_coding_projects():
    # coding projects with spaces becomes coding-projects which is in the list
    assert derive_agent_name("C:/Users/adity/coding projects/talktome") == "talktome"


def test_windows_path():
    # windows style path with backslashes
    assert derive_agent_name("C:\\Users\\adity\\myapp\\backend") == "myapp-backend"


def test_trailing_slash():
    # trailing slash should be stripped
    assert derive_agent_name("/home/user/myapp/backend/") == "myapp-backend"


def test_spaces_in_folder():
    # spaces in folder names become dashes
    assert derive_agent_name("/home/user/my app/back end") == "my-app-back-end"


def test_uppercase_normalized():
    # folder names should be lowercased
    assert derive_agent_name("/home/user/MyApp/Backend") == "myapp-backend"


def test_single_folder():
    # just a folder name with no parent
    assert derive_agent_name("myproject") == "myproject"


def test_root_level():
    # project directly under root
    assert derive_agent_name("/myproject") == "myproject"


def test_generic_parent_code():
    # code is generic
    assert derive_agent_name("/home/user/code/api") == "api"


def test_non_generic_parent():
    # a real parent folder should be used as prefix
    assert derive_agent_name("/home/user/company/microservice") == "company-microservice"


def test_generic_parent_src():
    # src is generic
    assert derive_agent_name("/home/user/src/webapp") == "webapp"
