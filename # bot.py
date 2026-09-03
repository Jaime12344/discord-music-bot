# bot.py
import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
import os
from collections import deque

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Fila global por servidor
queues = {}
# Status de loop por servidor
loop_status = {}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -bufsize 64k'
}

YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

def get_queue(guild_id):
    if guild_id not in queues:
        queues[guild_id] = deque()
    return queues[guild_id]

def get_loop(guild_id):
    if guild_id not in loop_status:
        loop_status[guild_id] = False
    return loop_status[guild_id]

class MusicPlayer:
    def __init__(self, ctx):
        self.ctx = ctx
        self.guild = ctx.guild
        self.voice_client = ctx.voice_client

    async def play_next(self, error=None):
        if error:
            print(f"Erro no player: {error}")
        guild_id = self.guild.id
        queue = get_queue(guild_id)
        loop = get_loop(guild_id)

        if loop and not queue:
            # Se estiver em loop e a fila estiver vazia, repete a última música (guardamos separadamente)
            # Para simplificar, vamos usar um truque: guardar a última música tocada
            if hasattr(self, 'last_song') and self.last_song:
                queue.append(self.last_song)
            else:
                return

        if queue:
            song = queue.popleft()
            self.last_song = song  # guarda para loop
            url = song['url']
            try:
                self.voice_client.play(
                    discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS),
                    after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(e), bot.loop)
                )
                await self.ctx.send(f"🎶 A tocar: **{song['title']}**")
            except Exception as e:
                await self.ctx.send(f"Erro ao tocar: {e}")
                await self.play_next()
        else:
            # Se não houver mais músicas e não estiver em loop, desconecta após 5 min
            await asyncio.sleep(300)
            if not self.voice_client.is_playing():
                await self.voice_client.disconnect()
                queues.pop(guild_id, None)
                loop_status.pop(guild_id, None)

@bot.command(name='play', aliases=['p'])
async def play(ctx, *, query):
    """Toca uma música do YouTube (URL ou pesquisa)"""
    if not ctx.author.voice:
        return await ctx.send("❗ Entra num canal de voz primeiro.")

    voice_channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        await voice_channel.connect()
    elif ctx.voice_client.channel != voice_channel:
        await ctx.voice_client.move_to(voice_channel)

    guild_id = ctx.guild.id
    queue = get_queue(guild_id)

    # Se já estiver a tocar, adiciona à fila
    if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
        async with ctx.typing():
            with youtube_dl.YoutubeDL(YDL_OPTIONS) as ydl:
                try:
                    info = ydl.extract_info(query, download=False)
                    if 'entries' in info:
                        info = info['entries'][0]
                    song = {
                        'url': info['url'],
                        'title': info.get('title', 'Desconhecido')
                    }
                    queue.append(song)
                    await ctx.send(f"✅ Adicionado à fila: **{song['title']}**")
                except Exception as e:
                    await ctx.send(f"❌ Erro: {e}")
        return

    # Se não está a tocar, toca imediatamente
    async with ctx.typing():
        with youtube_dl.YoutubeDL(YDL_OPTIONS) as ydl:
            try:
                info = ydl.extract_info(query, download=False)
                if 'entries' in info:
                    info = info['entries'][0]
                song = {
                    'url': info['url'],
                    'title': info.get('title', 'Desconhecido')
                }
                player = MusicPlayer(ctx)
                player.last_song = song
                ctx.voice_client.play(
                    discord.FFmpegPCMAudio(song['url'], **FFMPEG_OPTIONS),
                    after=lambda e: asyncio.run_coroutine_threadsafe(player.play_next(e), bot.loop)
                )
                await ctx.send(f"🎶 A tocar: **{song['title']}**")
            except Exception as e:
                await ctx.send(f"❌ Erro: {e}")

@bot.command(name='pause')
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸ Pausado.")
    else:
        await ctx.send("Nada a pausar.")

@bot.command(name='resume')
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶ A retomar.")
    else:
        await ctx.send("Nada a retomar.")

@bot.command(name='stop')
async def stop(ctx):
    guild_id = ctx.guild.id
    if ctx.voice_client:
        ctx.voice_client.stop()
        queues[guild_id] = deque()
        loop_status[guild_id] = False
        await ctx.send("⏹ Fila limpa e música parada.")
    else:
        await ctx.send("Não estou em nenhum canal.")

@bot.command(name='skip')
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏭ Música saltada.")
    else:
        await ctx.send("Nada a saltar.")

@bot.command(name='queue', aliases=['q'])
async def show_queue(ctx):
    guild_id = ctx.guild.id
    queue = get_queue(guild_id)
    if not queue:
        await ctx.send("📭 Fila vazia.")
    else:
        msg = "📜 **Fila:**\n" + "\n".join([f"{i+1}. {song['title']}" for i, song in enumerate(list(queue)[:10])])
        await ctx.send(msg)

@bot.command(name='loop')
async def loop(ctx):
    guild_id = ctx.guild.id
    current = get_loop(guild_id)
    loop_status[guild_id] = not current
    status = "ativado" if loop_status[guild_id] else "desativado"
    await ctx.send(f"🔄 Loop {status}.")

@bot.command(name='leave')
async def leave(ctx):
    if ctx.voice_client:
        guild_id = ctx.guild.id
        await ctx.voice_client.disconnect()
        queues.pop(guild_id, None)
        loop_status.pop(guild_id, None)
        await ctx.send("👋 Saí do canal.")
    else:
        await ctx.send("Não estou num canal.")

bot.run(os.getenv('DISCORD_TOKEN'))