from aiohttp import web
from pathlib import Path
import aiofiles
import asyncio
import time
import logging

logger = logging.getLogger(__name__)

CHUNK_SIZE = 100 * 1024


async def archive(request):
    archive_hash = request.match_info.get('archive_hash', '')
    if not Path(f'test_photos/{archive_hash}').exists():
        raise web.HTTPNotFound(text='Ошибка 404: Архив не существует или был удалён')
    response = web.StreamResponse()
    response.headers['Content-Disposition'] = f'attachment; filename="{archive_hash}.zip"'
    response.headers['Content-Type'] = 'application/zip, application/octet-stream'
    await response.prepare(request)
    process = await asyncio.create_subprocess_shell(
        f'zip -j -r - test_photos/{archive_hash}',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    while not process.stdout.at_eof():
        logger.info('Sending archive chunk...')
        chunk = await process.stdout.read(CHUNK_SIZE)
        await response.write(chunk)
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

    app = web.Application()
    app.add_routes([
        web.get('/', handle_index_page),
        web.get('/archive/{archive_hash}/', archive),
    ])
    web.run_app(app)
