"""Tests for workflow prompt templates."""

import pytest
from fastmcp.prompts import Message, PromptResult

from app.controllers.prompts.workflows import (
    build_set_workflow,
    deliver_set_workflow,
    expand_playlist_workflow,
    full_expansion_pipeline,
    improve_set_workflow,
)


class TestBuildSetWorkflow:
    """Test build_set_workflow prompt."""

    def test_returns_prompt_result(self):
        """Should return PromptResult with messages."""
        result = build_set_workflow("Test Playlist")
        assert isinstance(result, PromptResult)
        assert len(result.messages) == 2
        assert all(isinstance(msg, Message) for msg in result.messages)

    def test_first_message_is_user(self):
        """First message should be from user."""
        result = build_set_workflow("Test Playlist")
        assert result.messages[0].role == "user"

    def test_second_message_is_assistant(self):
        """Second message should be from assistant."""
        result = build_set_workflow("Test Playlist")
        assert result.messages[1].role == "assistant"

    def test_includes_playlist_name(self):
        """Should include the playlist name in the prompt."""
        result = build_set_workflow("My Techno Mix")
        user_message = result.messages[0].content.text
        assert "My Techno Mix" in user_message

    def test_includes_template_parameter(self):
        """Should include the template name in the prompt."""
        result = build_set_workflow("Test", template="peak_hour_60")
        user_message = result.messages[0].content.text
        assert "peak_hour_60" in user_message

    def test_includes_duration(self):
        """Should include the target duration in the prompt."""
        result = build_set_workflow("Test", duration_min=90)
        user_message = result.messages[0].content.text
        assert "90" in user_message

    def test_default_template(self):
        """Should use classic_60 as default template."""
        result = build_set_workflow("Test")
        user_message = result.messages[0].content.text
        assert "classic_60" in user_message

    def test_default_duration(self):
        """Should use 60 minutes as default duration."""
        result = build_set_workflow("Test")
        user_message = result.messages[0].content.text
        assert "60 minutes" in user_message

    def test_mentions_key_steps(self):
        """Should mention all key workflow steps."""
        result = build_set_workflow("Test")
        user_message = result.messages[0].content.text

        assert "Get Playlist" in user_message
        assert "Audit" in user_message
        assert "Build Set" in user_message
        assert "Review" in user_message
        assert "Deliver" in user_message or "deliver_set_workflow" in user_message

    def test_assistant_acknowledgment(self):
        """Assistant message should acknowledge the task."""
        result = build_set_workflow("Test Playlist")
        assistant_message = result.messages[1].content.text
        assert "build" in assistant_message.lower()
        assert "set" in assistant_message.lower()


class TestExpandPlaylistWorkflow:
    """Test expand_playlist_workflow prompt."""

    def test_returns_prompt_result(self):
        """Should return PromptResult with messages."""
        result = expand_playlist_workflow("Source Playlist")
        assert isinstance(result, PromptResult)
        assert len(result.messages) == 2
        assert all(isinstance(msg, Message) for msg in result.messages)

    def test_includes_playlist_name(self):
        """Should include the playlist name in the prompt."""
        result = expand_playlist_workflow("My Collection")
        user_message = result.messages[0].content.text
        assert "My Collection" in user_message

    def test_includes_target_count(self):
        """Should include the target count in the prompt."""
        result = expand_playlist_workflow("Test", target_count=200)
        user_message = result.messages[0].content.text
        assert "200" in user_message

    def test_default_target_count(self):
        """Should use 100 as default target count."""
        result = expand_playlist_workflow("Test")
        user_message = result.messages[0].content.text
        assert "100" in user_message

    def test_mentions_key_steps(self):
        """Should mention all key workflow steps."""
        result = expand_playlist_workflow("Test")
        user_message = result.messages[0].content.text

        assert "Audit" in user_message
        assert "Find Similar" in user_message or "similar" in user_message
        assert "Import" in user_message
        assert "Download" in user_message
        assert "Analyze" in user_message or "Analysis" in user_message
        assert "Classify" in user_message or "classify" in user_message


class TestImproveSetWorkflow:
    """Test improve_set_workflow prompt."""

    def test_returns_prompt_result(self):
        """Should return PromptResult with messages."""
        result = improve_set_workflow("My Set")
        assert isinstance(result, PromptResult)
        assert len(result.messages) == 2

    def test_includes_set_name(self):
        """Should include the set name in the prompt."""
        result = improve_set_workflow("Peak Hour Mix")
        user_message = result.messages[0].content.text
        assert "Peak Hour Mix" in user_message

    def test_mentions_key_steps(self):
        """Should mention all key workflow steps."""
        result = improve_set_workflow("Test")
        user_message = result.messages[0].content.text

        assert "Review" in user_message
        assert "Explain" in user_message or "explain" in user_message
        assert "Replacement" in user_message or "replacement" in user_message
        assert "Rebuild" in user_message or "rebuild" in user_message
        assert "Compare" in user_message or "compare" in user_message

    def test_mentions_transition_analysis(self):
        """Should mention transition analysis and scoring."""
        result = improve_set_workflow("Test")
        user_message = result.messages[0].content.text
        assert "transition" in user_message.lower()


class TestDeliverSetWorkflow:
    """Test deliver_set_workflow prompt."""

    def test_returns_prompt_result(self):
        """Should return PromptResult with messages."""
        result = deliver_set_workflow("Final Set")
        assert isinstance(result, PromptResult)
        assert len(result.messages) == 2

    def test_includes_set_name(self):
        """Should include the set name in the prompt."""
        result = deliver_set_workflow("Production Mix")
        user_message = result.messages[0].content.text
        assert "Production Mix" in user_message

    def test_sync_ym_false_by_default(self):
        """Should not mention YM sync by default."""
        result = deliver_set_workflow("Test")
        user_message = result.messages[0].content.text
        assert "7. **YM Sync**" not in user_message

    def test_sync_ym_true_adds_step(self):
        """Should include YM sync step when enabled."""
        result = deliver_set_workflow("Test", sync_ym=True)
        user_message = result.messages[0].content.text
        assert "YM Sync" in user_message or "Yandex Music" in user_message

    def test_assistant_mentions_sync_when_enabled(self):
        """Assistant should acknowledge YM sync when enabled."""
        result = deliver_set_workflow("Test", sync_ym=True)
        assistant_message = result.messages[1].content.text
        assert "Yandex Music" in assistant_message or "sync" in assistant_message.lower()

    def test_mentions_key_steps(self):
        """Should mention all key workflow steps."""
        result = deliver_set_workflow("Test")
        user_message = result.messages[0].content.text

        assert "Score" in user_message or "transition" in user_message.lower()
        assert "Conflict" in user_message or "conflict" in user_message.lower()
        assert "Deliver" in user_message or "deliver" in user_message.lower()
        assert "Export" in user_message or "export" in user_message.lower()

    def test_mentions_export_formats(self):
        """Should mention export formats (M3U8, JSON, etc.)."""
        result = deliver_set_workflow("Test")
        user_message = result.messages[0].content.text
        assert "m3u8" in user_message.lower() or "M3U8" in user_message
        assert "json" in user_message.lower() or "JSON" in user_message


class TestFullExpansionPipeline:
    """Test full_expansion_pipeline prompt."""

    def test_returns_prompt_result(self):
        """Should return PromptResult with messages."""
        result = full_expansion_pipeline("Source")
        assert isinstance(result, PromptResult)
        assert len(result.messages) == 2

    def test_includes_source_playlist(self):
        """Should include the source playlist name."""
        result = full_expansion_pipeline("TECHNO FOR DJ SETS")
        user_message = result.messages[0].content.text
        assert "TECHNO FOR DJ SETS" in user_message

    def test_includes_target_per_subgenre(self):
        """Should include the target count per subgenre."""
        result = full_expansion_pipeline("Source", target_per_subgenre=75)
        user_message = result.messages[0].content.text
        assert "75" in user_message

    def test_default_target_per_subgenre(self):
        """Should use 50 as default target per subgenre."""
        result = full_expansion_pipeline("Source")
        user_message = result.messages[0].content.text
        assert "50" in user_message

    def test_mentions_key_steps(self):
        """Should mention all major pipeline steps."""
        result = full_expansion_pipeline("Source")
        user_message = result.messages[0].content.text

        assert "Audit" in user_message
        assert "Discover" in user_message or "similar" in user_message.lower()
        assert "Import" in user_message
        assert "Download" in user_message
        assert "Analyze" in user_message
        assert "Classify" in user_message
        assert "Distribute" in user_message or "distribute" in user_message.lower()

    def test_mentions_15_subgenres(self):
        """Should mention the 15 techno subgenres."""
        result = full_expansion_pipeline("Source")
        user_message = result.messages[0].content.text
        assert "15" in user_message
        assert "subgenre" in user_message.lower()

    def test_warns_about_long_duration(self):
        """Should warn that this is a long-running pipeline."""
        result = full_expansion_pipeline("Source")
        user_message = result.messages[0].content.text
        assert "hour" in user_message.lower() or "time" in user_message.lower()

    def test_assistant_acknowledges_long_duration(self):
        """Assistant should acknowledge the long duration."""
        result = full_expansion_pipeline("Source")
        assistant_message = result.messages[1].content.text
        assert "time" in assistant_message.lower() or "pipeline" in assistant_message.lower()


class TestMessageStructure:
    """Test common Message structure patterns."""

    @pytest.mark.parametrize(
        "prompt_func,args",
        [
            (build_set_workflow, ("Test",)),
            (expand_playlist_workflow, ("Test",)),
            (improve_set_workflow, ("Test",)),
            (deliver_set_workflow, ("Test",)),
            (full_expansion_pipeline, ("Test",)),
        ],
    )
    def test_all_prompts_return_two_messages(self, prompt_func, args):
        """All workflow prompts should return exactly 2 messages."""
        result = prompt_func(*args)
        assert isinstance(result, PromptResult)
        assert len(result.messages) == 2

    @pytest.mark.parametrize(
        "prompt_func,args",
        [
            (build_set_workflow, ("Test",)),
            (expand_playlist_workflow, ("Test",)),
            (improve_set_workflow, ("Test",)),
            (deliver_set_workflow, ("Test",)),
            (full_expansion_pipeline, ("Test",)),
        ],
    )
    def test_all_prompts_have_user_then_assistant(self, prompt_func, args):
        """All prompts should follow user → assistant pattern."""
        result = prompt_func(*args)
        assert result.messages[0].role == "user"
        assert result.messages[1].role == "assistant"

    @pytest.mark.parametrize(
        "prompt_func,args",
        [
            (build_set_workflow, ("Test",)),
            (expand_playlist_workflow, ("Test",)),
            (improve_set_workflow, ("Test",)),
            (deliver_set_workflow, ("Test",)),
            (full_expansion_pipeline, ("Test",)),
        ],
    )
    def test_all_prompts_have_non_empty_content(self, prompt_func, args):
        """All messages should have non-empty content."""
        result = prompt_func(*args)
        for msg in result.messages:
            assert msg.content
            assert len(msg.content.text) > 0


class TestPromptMetadata:
    """Test prompt registration and metadata."""

    def test_all_prompts_have_docstrings(self):
        """All prompt functions should have docstrings."""
        assert build_set_workflow.__doc__
        assert expand_playlist_workflow.__doc__
        assert improve_set_workflow.__doc__
        assert deliver_set_workflow.__doc__
        assert full_expansion_pipeline.__doc__

    def test_docstrings_include_steps(self):
        """Docstrings should mention the workflow steps."""
        assert "Steps:" in build_set_workflow.__doc__
        assert "Steps:" in expand_playlist_workflow.__doc__
        assert "Steps:" in improve_set_workflow.__doc__
        assert "Steps:" in deliver_set_workflow.__doc__
        assert "Steps:" in full_expansion_pipeline.__doc__

    def test_docstrings_document_parameters(self):
        """Docstrings should document all parameters."""
        # Check that Args: section exists and parameters are documented
        assert "Args:" in build_set_workflow.__doc__
        assert "playlist_name" in build_set_workflow.__doc__
        assert "template" in build_set_workflow.__doc__

        assert "Args:" in expand_playlist_workflow.__doc__
        assert "target_count" in expand_playlist_workflow.__doc__

        assert "Args:" in deliver_set_workflow.__doc__
        assert "sync_ym" in deliver_set_workflow.__doc__
