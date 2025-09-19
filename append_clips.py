import os
import shutil
from moviepy.editor import (
    VideoFileClip,
    concatenate_videoclips,
    vfx,
)  # ## MODIFIED ## Added vfx

# --- 1. SET YOUR PATHS AND SETTINGS HERE ---

main_videos_folder = r"D:\Santiago Marin\Clips\Raw_clips"
clip_to_append_path = (
    r"D:\Santiago Marin\Clips\outro\Spider_Men_s_Marimba_Concert_Call_to_Action.mp4"
)
output_folder_long_clips = r"D:\Santiago Marin\Clips\Final_clips"
output_folder_short_clips = r"D:\Santiago Marin\Clips\Short_clips"
max_short_clip_duration = 16

# --- 2. THE SCRIPT LOGIC ---


def process_videos():
    """
    Sorts videos by duration. Short videos are copied to one folder,
    while an outro is appended to long videos and saved in another.
    """
    for folder in [output_folder_long_clips, output_folder_short_clips]:
        if not os.path.exists(folder):
            os.makedirs(folder)
            print(f"Created new directory: '{folder}'")

    try:
        append_clip = VideoFileClip(clip_to_append_path)
    except Exception as e:
        print(f"❌ Error: Could not load the outro clip from '{clip_to_append_path}'.")
        return

    if not os.path.isdir(main_videos_folder):
        print(f"❌ Error: The source folder '{main_videos_folder}' was not found.")
        return

    video_extensions = (".mp4", ".mov", ".avi", ".mkv", ".wmv", ".webm")
    print(f"\nScanning '{main_videos_folder}' for videos...")

    for filename in os.listdir(main_videos_folder):
        if filename.lower().endswith(video_extensions):
            main_video_path = os.path.join(main_videos_folder, filename)
            main_clip = None

            try:
                main_clip = VideoFileClip(main_video_path)

                if main_clip.duration <= max_short_clip_duration:
                    print(
                        f"-> '{filename}' is short ({main_clip.duration:.1f}s). Copying..."
                    )
                    destination_path = os.path.join(output_folder_short_clips, filename)
                    shutil.copy(main_video_path, destination_path)
                    print(f"✅ Copied to '{output_folder_short_clips}'")

                else:
                    print(
                        f"-> '{filename}' is long ({main_clip.duration:.1f}s). Appending outro..."
                    )

                    # ## MODIFIED ## - Standardize the outro clip to match the main clip
                    # This is the fix for the glitching
                    standardized_append_clip = append_clip.set_fps(main_clip.fps)
                    if append_clip.size != main_clip.size:
                        print(
                            f"   Resizing outro from {append_clip.size} to {main_clip.size}"
                        )
                        standardized_append_clip = standardized_append_clip.resize(
                            main_clip.size
                        )

                    # ## MODIFIED ## - Combine with the standardized clip
                    final_clip = concatenate_videoclips(
                        [main_clip, standardized_append_clip]
                    )

                    output_filename = f"{os.path.splitext(filename)[0]}_appended.mp4"
                    output_path = os.path.join(
                        output_folder_long_clips, output_filename
                    )

                    # Add audio_codec='aac' for better compatibility
                    final_clip.write_videofile(
                        output_path, codec="libx264", audio_codec="aac"
                    )
                    final_clip.close()

                    print(f"✅ Saved new file to '{output_folder_long_clips}'")

            except Exception as e:
                print(f"⚠️ Failed to process '{filename}'. Error: {e}")

            finally:
                if main_clip:
                    main_clip.close()

    append_clip.close()
    print("\n🎉 All done! Your original files are untouched.")


if __name__ == "__main__":
    process_videos()
