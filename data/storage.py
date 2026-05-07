from core.data_manager import (
    init_db, _get_conn, count_messages, get_all_messages,
    commit_messages, save_messages_batch_fast, update_sync_progress,
    get_last_sync_time, get_all_settings, get_all_keywords,
    add_keyword, delete_keyword, toggle_keyword,
    get_all_blacklist, add_blacklist, delete_blacklist,
    save_snapshot, load_snapshot, is_db_initialized,
    get_cached_avatar_path, save_avatar_cache,
    save_setting, get_messages_by_chat, get_urgent_messages,
    update_message_meta,
    SNAPSHOT_PATH, DB_PATH, AVATAR_CACHE_DIR
)
