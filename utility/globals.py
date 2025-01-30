

# ──────────────────────────
# Global
# ──────────────────────────
player_count = 0
ext_chunk_count = 0

# ──────────────────────────
# Single Chat Window *per channel*
# ──────────────────────────
# We'll store data in a dictionary keyed by channel ID:
#   channel_id -> {
#       "message": discord.Message,
#       "expires_at": float,
#       "task": asyncio.Task
#   }
chat_windows = {}