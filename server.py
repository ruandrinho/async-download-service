from aiohttp import web
from pathlib import Path
from random import randint
from environs import Env
from functools import partial
import aiofiles
import asyncio
import logging
import argparse

logger = logging.getLogger(__name__)


async def archive(request, chunk_size, unstable_connection_simulation, photos_parent_dir):
    archive_hash = request.match_info['archive_hash']
    if not Path(f'{photos_parent_dir}/{archive_hash}').exists():
        raise web.HTTPNotFound(text='Ошибка 404: Архив не существует или был удалён')
    response = web.StreamResponse()
    response.headers['Content-Disposition'] = f'attachment; filename="{archive_hash}.zip"'
    response.headers['Content-Type'] = 'application/zip, application/octet-stream'
    await response.prepare(request)
    process = await asyncio.create_subprocess_exec(
        'zip', '-r', '-', '.',
        cwd=f'{photos_parent_dir}/{archive_hash}',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    try:
        while not process.stdout.at_eof():
            logger.info('Sending archive chunk...')
            chunk = await process.stdout.read(chunk_size)
            await response.write(chunk)
            if unstable_connection_simulation:
                await asyncio.sleep(randint(0, 5))
    except asyncio.CancelledError:
        logger.info('Download was interrupted')
        raise
    except BaseException:
        logger.info('Unknown error')
    finally:
        if process.returncode:
            process.kill()
            outs, errs = await process.communicate()
    return response


async def handle_index_page(request):
    async with aiofiles.open('index.html', mode='r') as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents, content_type='text/html')


if __name__ == '__main__':

    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    env = Env()
    env.read_env()

    archive_arguments = {}
    chunk_size = env.int('CHUNK_SIZE', default=100000)
    enable_logging = env.bool('ENABLE_LOGGING', default=True)
    unstable_connection_simulation = env.bool('UNSTABLE_CONNECTION_SIMULATION', default=False)
    photos_parent_dir = env('PHOTOS_PARENT_DIR', default='photos')

    parser = argparse.ArgumentParser(description='Make archive of a folder and stream to a client')
    parser.add_argument('--nologs', '-n', action='store_true', help='Disable logging')
    parser.add_argument('--unstable', '-u', action='store_true', help='Imitate unstable connection')
    parser.add_argument('--dir', '-d', action='store', help='Parent folder of photos folders')
    args = parser.parse_args()
    if args.nologs or not enable_logging:
        logger.setLevel(logging.ERROR)
    if args.unstable is True:
        unstable_connection_simulation = True
    if args.dir:
        photos_parent_dir = args.dir

    app = web.Application()
    app.add_routes([
        web.get('/', handle_index_page),
        web.get(
            '/archive/{archive_hash}/',
            partial(
                archive,
                chunk_size=chunk_size,
                unstable_connection_simulation=unstable_connection_simulation,
                photos_parent_dir=photos_parent_dir
            )
        ),
    ])
    try:
        web.run_app(app)
    except KeyboardInterrupt:
        logger.info('Server is terminated')
