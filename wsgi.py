import os
from app import create_app

app = create_app(os.environ.get("FLASK_ENV", "development"))

def prewarm_cache():
    """Pre-warm in-memory caches to ensure initial and subsequent requests are served in milliseconds."""
    with app.app_context():
        try:
            from app.api.teams import _load_teams_into_cache
            from app.api.members import _load_all_members_into_cache
            from app.api.events import _load_events_into_cache
            from app.services.community_service import _load_communities_into_cache
            from app.models.user import User
            _load_teams_into_cache()
            _load_all_members_into_cache()
            _load_events_into_cache()
            _load_communities_into_cache()
            admin_user = User.query.filter_by(role="admin").first() or User.query.filter_by(role="president").first()
            if admin_user:
                from app.services.documentation_service import DocumentationService
                from app.services.media_service import MediaService
                from app.services.mc_template_service import McTemplateService
                from app.services.mc_script_service import McScriptService
                DocumentationService.list_folders_data(admin_user)
                DocumentationService.list_reports_data(admin_user)
                MediaService.list_folders_data(admin_user)
                McTemplateService.seed_default_templates()
                McTemplateService.get_event_types_catalog()
                McTemplateService.list_templates(admin_user)
                McScriptService.get_dashboard_summary(admin_user)
                McScriptService.list_scripts(admin_user)
                McScriptService.list_folders(admin_user)
        except Exception as e:
            app.logger.warning(f"Cache pre-warming notice: {e}")

if __name__ == "__main__":
    import threading
    t = threading.Thread(target=prewarm_cache, daemon=True)
    t.start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=app.config.get("DEBUG", False))
