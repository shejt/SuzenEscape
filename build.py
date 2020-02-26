#!/usr/bin/env python3

try:
    import argparse
    import docker
    import logging
    import yaml
except ImportError:
    print('Import error.\nYou need to install requirements.\npip3 install -r requirements.txt')
    exit(1)


def build(level, registry_url, args):
    try:
        image_tag = f'{registry_url}/suzenescape/{level["name"]}'

        _, build_log = client.images.build(
            path=f'chains/chain{level["chain"].zfill(2)}/level{level["level"]}',
            tag=image_tag,
            buildargs={
                'USERNAME': level['name'],
                'CONFIG': level.get('config', 'NONE'),
                'USERHOME': 'root' if level.get('rohome') else level['name'],
                'FLAG': level.get('flag', 'NONE'),
            },
            rm=True,
            forcerm=True,
        )

        if args.verbose:
            build_log_string = ''.join((item.get('stream', '') for item in build_log))[:-1]
            logging.info(f'{image_tag} build log:\n{build_log_string}')

        if not args.build_only:
            push(image_tag)

    except (docker.errors.BuildError, docker.errors.APIError) as exc:
        logging.error('build error:')
        logging.error(exc)
        exit(1)


def push(image):
    result = client.images.push(image)
    logging.info('push status:')
    logging.info(result[:-1])


def argp():
    parser = argparse.ArgumentParser()

    parser.add_argument('-b', '--build_only', help='build only, not push images', action='store_true')
    # parser.add_argument('-t', '--token', help='token, used as message to encrypt')
    parser.add_argument('-v', '--verbose', help='log enable', action='count')
    # parser.add_argument('-f', '--vars-yaml', help='path to yaml level vars file')
    parser.add_argument('task', nargs='+', help='task to build list')

    return parser.parse_args()


def query_add(qtask):
    build_query[qtask] = levels_map[qtask]
    build_query[qtask]['level'] = qtask
    try:
        servers = levels_map[qtask]['servers']
    except KeyError:
        servers = list()
        pass
    for server in servers:
        stask = server['name'][len('suzen') :]
        build_query[stask] = server
        build_query[stask]['level'] = stask
        build_query[stask]['chain'] = levels_map[qtask]['chain']


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)

    args = argp()

    client = docker.client.from_env()
    try:
        client.ping()
    except docker.errors.APIError as exc:
        logging.error('docker client not init')
        logging.error(exc)
        exit(1)

    logging.info('Start')

    try:
        with open('ansible/vars.yaml', 'r') as stream:
            yml = yaml.load(stream, Loader=yaml.BaseLoader)
    except yaml.YAMLError as exc:
        logging.error(exc)
        exit(1)

    registry_url = yml['registry_url']

    levels_map = {level['name'][len('suzen') :]: level for level in yml['levels']}

    build_query = dict()

    if args.task[0] == 'all':
        for task in levels_map.keys():
            query_add(task)
    else:
        for task in args.task:
            if task not in levels_map.keys():
                logging.warning(f'{task} in not available: skipping')
                continue

            query_add(task)

    for level in build_query:
        logging.info(f'build level {level}')
        build(build_query[level], registry_url, args)
