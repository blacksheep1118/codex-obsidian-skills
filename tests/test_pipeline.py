from pathlib import Path

from scripts.ppt_to_obsidian_pipeline import PipelineConfig, run


def test_pipeline_extracts_cleans_and_writes_manifest(tmp_path: Path):
    config = PipelineConfig(
        source=Path("examples/sample-course/raw/sample_course.pptx"),
        output_dir=tmp_path / "out",
        mode="course-notes",
        unicode_math=True,
        course_name="示例课程",
    )

    processed = run(config)

    assert len(processed) == 1
    assert (config.output_dir / "raw_extracted" / "sample_course.md").exists()
    assert (config.output_dir / "cleaned" / "sample_course.md").exists()
    assert (config.output_dir / "pipeline_manifest.md").exists()
    assert (config.output_dir / "notes_skeleton" / "00_课程总览.md").exists()
