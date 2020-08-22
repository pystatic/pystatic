import site


def get_sitepkg():
    return [site.getusersitepackages()] + site.getsitepackages()
