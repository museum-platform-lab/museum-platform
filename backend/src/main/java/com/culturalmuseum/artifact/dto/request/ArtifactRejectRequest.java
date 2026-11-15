package com.culturalmuseum.artifact.dto.request;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "Request payload for rejecting an artifact")
public class ArtifactRejectRequest {

    @Schema(description = "Reason for rejection or feedback to the contributor", example = "Image is too blurry, please provide a higher quality image.", requiredMode = Schema.RequiredMode.REQUIRED)
    private String adminNote;

    public ArtifactRejectRequest() {
    }

    public String getAdminNote() {
        return adminNote;
    }

    public void setAdminNote(String adminNote) {
        this.adminNote = adminNote;
    }
}
