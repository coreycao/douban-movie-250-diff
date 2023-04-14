def log(*args):
    print("Movie250Diff: ", *args)


def write_text(file_name, method, text):
    """
    method: 'a'-append,
            'w'-overwrite
    """
    with open(file_name, method, encoding='utf-8') as f:
        f.write(text)

