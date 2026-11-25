# Video number -> Google Drive link mapping
# Naye video ka link add karne ke liye, bas neeche ek naya entry jod dein

video_links = {
    1: "",
    2: "",
}


def get_video_link(video_number):
    try:
        return video_links.get(int(video_number))
    except (ValueError, TypeError):
        return None