#!/usr/bin/env python3
"""
 Generate a tree of HTML index files from an actual file structure
 or a tree of files representing a file structure.
"""

from jinja2 import Environment
import os
import sys
from datetime import datetime
import time
import argparse
import re
import logging
import urllib.parse

# Python 2/3 compatible hack
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

#sys.setrecursionlimit(2100000000)

configuration = None

def parse_arguments():
    global configuration
    global logger

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "path",
        help="Top directory for writing index files.")
    parser.add_argument(
        "base_path",
        default=None,
        nargs="?",
        help="The part of the path to remove when generating indices")
    parser.add_argument(
        "--file-metadata", "-f",
        default=None,
        help="A file containing data describing the tree to index.")
    parser.add_argument(
        "--metadata-delimiter", "-m",
        default=";",
        help="Character which seperates fields in the file metadata.")
    parser.add_argument(
            "--exclude-path", "-x",
            default=None,
            action='append',
            help="paths to exclude from indexing")
    parser.add_argument(
        "--noop", "-n",
        help="Only print files to be created without writing them to disk",
        action="store_true")
    parser.add_argument(
        "--verbose", "-v",
        help="Verbose output. Repeat (up to -vvv) for more verbosity",
        action="count")
    configuration = parser.parse_args()

    logger = logging.getLogger(__name__)
    logger_format = '%(filename)s: %(levelname)s %(message)s'

    if configuration.verbose == 1:
        logging.basicConfig(level=logging.WARNING, format=logger_format)
    elif configuration.verbose == 2:
        logging.basicConfig(level=logging.INFO, format=logger_format)
    elif configuration.verbose > 2:
        logging.basicConfig(level=logging.DEBUG, format=logger_format)
    else:
        logging.basicConfig(level=logging.ERROR, format=logger_format)

    if configuration.base_path is None:
        configuration.base_path = configuration.path


def index_link(prefix, current_order_by, new_order_by, reverse_order):
    if current_order_by == new_order_by:
        return index_file_name(prefix, current_order_by, not reverse_order)
    else:
        return index_file_name(prefix, new_order_by, False)


def render_index(prefix, order_by, contents, reverse_order, base_path):
    """
      use a templating library to turn a prefix and a list of contents
      into an HTML directory index
    """
    logger.debug('rendering index for {prefix} ordered by {order_by} and reverse_order={reverse_order}'.format(prefix=prefix, order_by=order_by, reverse_order=reverse_order))

    formatted_contents = format_file_details(contents)

    # Remove the base path from the prefix to avoid putting the full
    # filesystem path in the index
    path = '' if prefix == base_path else prefix.replace(base_path, '')
    parent_directory = '/'.join(path.split('/')[:-1])

    # dumb hack because paths are prefixed with / when run on os x but not linux
    root_prefix = '' if path.startswith('/') else '/'

    index_by = {}
    index_by['lastModified'] = index_link(path, order_by, 'lastModified', reverse_order)
    index_by['name'] = index_link(path, order_by, 'name', reverse_order)
    index_by['size'] = index_link(path, order_by, 'size', reverse_order)
    logging.debug('path: {path}'.format(path=path))
    logging.debug('contents: {contents}'.format(contents=contents))
    logging.debug('parent_directory: {parent_directory}'.format(parent_directory=parent_directory))

    html = []
    html.append("<html>")
    html.append("<head><title>Index of {}{}{}</title></head>".format(root_prefix, path, '/' if path != '' else ''))
    html.append("<body bgcolor=\"white\">")
    html.append("<h1>Index of {}{}{}</h1>".format(root_prefix, path, '/' if path != '' else ''))
    html.append("<hr><pre>")
    if path != '':
        html.append("<a href=\"../index.html\">../</a>")
    for item in formatted_contents:
        if item['icon'] == 'folder.gif':
            html.append("<a href=\"{}/index.html\">{}/</a>{} {} {:>19}".format(urllib.parse.quote(item["name"]), item["displayname"], ' '*(49-len(item["displayname"])), item["lastModified"], '-'))
        else:
            html.append("<a href=\"{}\">{}</a>{} {} {:>19}".format(urllib.parse.quote(item["name"]), item["displayname"], ' '*(50-len(item["displayname"])), item["lastModified"], item["size"]))
    html.append("</pre><hr>")
    html.append("</body></html>")

    return "\n".join(html)


def index_file_name(prefix, order_by, reverse_order):
    order_suffix = "_reverse" if reverse_order else ""
    file_name = 'index' + '_by_' + order_by + order_suffix + '.html'
    return file_name if len(prefix) == 0 else prefix + '/' + file_name


def format_date(d):
    return datetime.utcfromtimestamp(int(d)).strftime('%d-%b-%Y %H:%M')


def format_size(a_number, suffix='B'):
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(a_number) < 1024.0:
            return '{:>3.1f}{}{}'.format(a_number, unit, suffix)
        a_number /= 1024.0
    return '{:1f}{}{}'.format(a_number, 'Yi', suffix)


def format_file_details(file_details):
    out = []
    for k in file_details:
        out.append ({
        'name': k['name'],
        'displayname': k['name'] if len(k['name']) <= 50 else k['name'][:47] + '..&gt;',
        'lastModified': format_date(k['lastModified']),
        'size': k['size'],
        'icon': k['icon']
    })
    return out


def file_information(full_path, file, last_modified=None, size=None):
    if last_modified is None:
        last_modified = os.path.getmtime(full_path)
    if size is None:
        size = os.path.getsize(full_path)
    icon = 'folder.gif' if os.path.isdir(full_path) else 'unknown.gif'

    return {
        'name': file,
        'lastModified': last_modified,
        'size': size,
        'icon': icon
    }


def string_to_epoch_seconds(string, format):
    utc_time = datetime.strptime(string, format)
    epoch_time = (utc_time - datetime(1970, 1, 1)).total_seconds()

    return epoch_time


def is_excluded_file(file_name):
    """
      A list of file names to exclude from the generated index files.
    """
    excluded_file_names = [
        "index.html",
        "index_by_lastModified.html",
        "index_by_lastModified_reverse.html",
        "index_by_name.html",
        "index_by_name_reverse.html",
        "index_by_size.html",
        "index_by_size_reverse.html"
    ]

    return file_name in excluded_file_names

def is_excluded_path(path):
    # for the ability to match more exactly, get rid of base_path
    path = path.replace(configuration.base_path, '')
    if configuration.exclude_path is not None:
        # similar to configuration[exclude_path].select { |x| x =~ /^\/#{path}/ }.any? in ruby
        return len(filter(lambda x: re.match('/{path}'.format(path=x), path), configuration.exclude_path)) != 0

    return False


def parse_file_metadata(current_path, file_metadata):
    last_modified_format = "%Y-%m-%d:%H:%M"
    file_details = []
    # generate indexes for current path
    with open("/".join((current_path, file_metadata))) as file_handle:
        for line in file_handle:
            line = line.strip()
            ##
            # Metadata is either
            # file_name;last_modified_date;last_modified_time;size
            # or simply,
            # directory_name
            #
            metadata = line.split(configuration.metadata_delimiter)
            file_name = metadata[0]
            if is_excluded_file(file_name):
                continue

            last_modified = time.time()
            size = 0
            full_path = os.path.join(current_path, file_name)

            if len(metadata) != 1:
                last_modified = string_to_epoch_seconds(
                    metadata[1] + ":" + metadata[2],
                    last_modified_format)
                size = int(metadata[3])

            file_details.append(
                file_information(full_path, file_name, last_modified, size))

    return file_details


def gather_file_details(current_path, list_of_files):
    file_details = []
    # generate indexes for current path
    for file_name in list_of_files:
        # add size, lastModified, file/folder type to metadata
        full_path = os.path.join(current_path, file_name)
        if file_name.startswith('.'):
            continue
        if is_excluded_file(file_name):
            continue
        if is_excluded_path(full_path):
            logging.debug('excluding: {path}'.format(path=full_path))
            continue
        if os.path.exists(full_path):
            icon = 'folder.gif' if os.path.isdir(full_path) else 'unknown.gif'
            file_details.append(file_information(full_path, file_name))
        else:
            logging.error('skipping \'{}\' because the file cannot be read'.format(full_path))

    return file_details


def make_index_files(base_path, current_path, file_details):
    order_by = 'name'
    reverse_order = False
    file_name = os.path.join(current_path, 'index.html')
    rendered_html = render_index(current_path, order_by, file_details,
                                 reverse_order, base_path)
    if configuration.noop:
        logging.info('Would create: {}'.format(file_name))
    else:
        logging.info('Wrote: {}'.format(file_name))
        index_file = open(file_name, 'w')
        index_file.write(rendered_html)
        index_file.close()


def traverse_tree(base_path, current_path, file_metadata=None):
    contents = os.listdir(current_path)

    if is_excluded_path(current_path):
        logging.debug('excluding: {path}'.format(path=current_path))
        return None

    if file_metadata:
        file_details = parse_file_metadata(current_path, file_metadata)
    else:
        file_details = gather_file_details(current_path, contents)

    make_index_files(base_path, current_path, file_details)
    for file_name in contents:
        absolute_path = os.path.join(current_path, file_name)
        if os.path.isdir(absolute_path):
            traverse_tree(base_path, absolute_path, file_metadata)


def validate_input(configuration):
    script = os.path.basename(sys.argv[0])

    if not os.path.isdir(configuration.path):
        sys.exit('{}: ERROR {} is not a directory'.format(script, configuration.path))


if __name__ == '__main__':
    parse_arguments()
    validate_input(configuration)
    traverse_tree(configuration.base_path, configuration.path, configuration.file_metadata)
