import type {
    CheckResponse,
    ProfileId,
} from "@/types";

export async function requestDocumentCheck(
    file: File,
    profileId: ProfileId,
): Promise<CheckResponse> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("profile_id", profileId);

    const response = await fetch("/api/check", {
        method: "POST",
        body: formData,
    });

    const data: unknown = await response.json();

    if (!response.ok) {
        let message = "Не удалось проверить документ.";

        if (
            typeof data === "object"
            && data !== null
            && "detail" in data
            && typeof data.detail === "string"
            && data.detail
        ) {
            message = data.detail;
        }

        throw new Error(message);
    }

    return data as CheckResponse;
}