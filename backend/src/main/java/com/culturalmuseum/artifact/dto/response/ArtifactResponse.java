package com.culturalmuseum.artifact.dto.response;

import com.culturalmuseum.artifact.entity.Artifact;
import io.swagger.v3.oas.annotations.media.Schema;

import java.time.OffsetDateTime;

@Schema(description = "Artifact response payload")
public class ArtifactResponse {

    @Schema(description = "Unique ID of the artifact", example = "1")
    private Long id;

    @Schema(description = "Name of the artifact", example = "Dong Son Bronze Drum")
    private String name;

    @Schema(description = "Brief summary", example = "Iconic bronze drum representing Dong Son culture")
    private String shortDescription;

    @Schema(description = "Detailed description", example = "The Dong Son bronze drums were created...")
    private String description;

    @Schema(description = "Category tags", example = "Bronze Age, Archeological Relic")
    private String categories;

    @Schema(description = "URL of main image", example = "https://example.com/images/dong-son-drum.jpg")
    private String mainImageUrl;

    @Schema(description = "URLs of supporting images", example = "https://example.com/img1.jpg,https://example.com/img2.jpg")
    private String supportingImages;

    @Schema(description = "Author or craftsman", example = "Lac Viet People")
    private String author;

    @Schema(description = "Display name of contributor", example = "Nguyen Van An")
    private String contributorName;

    @Schema(description = "ID of contributor account (if registered user)", example = "5")
    private Long contributorId;

    @Schema(description = "Historical era", example = "Dong Son Culture (c. 1000 BC - 1st century AD)")
    private String artifactEra;

    @Schema(description = "Public release / discovery date", example = "1924")
    private String publicDate;

    @Schema(description = "Gallery location", example = "Exhibition Hall 1")
    private String location;

    @Schema(description = "Approval status (PENDING, APPROVED, REJECTED)", example = "APPROVED")
    private String approvalStatus;

    @Schema(description = "Admin review note / rejection reason", example = "Verified authentic")
    private String adminNote;

    @Schema(description = "Record creation timestamp")
    private OffsetDateTime createdAt;

    @Schema(description = "Last update timestamp")
    private OffsetDateTime updatedAt;

    @Schema(description = "Approval timestamp")
    private OffsetDateTime approvedAt;

    public ArtifactResponse() {
    }

    // Static mapper method
    public static ArtifactResponse fromEntity(Artifact artifact) {
        if (artifact == null) {
            return null;
        }

        ArtifactResponse response = new ArtifactResponse();
        response.setId(artifact.getId());
        response.setName(artifact.getName());
        response.setShortDescription(artifact.getShortDescription());
        response.setDescription(artifact.getDescription());
        response.setCategories(artifact.getCategories());
        response.setMainImageUrl(artifact.getMainImageUrl());
        response.setSupportingImages(artifact.getSupportingImages());
        response.setAuthor(artifact.getAuthor());

        // Gán thông tin contributor
        if (artifact.getContributor() != null) {
            response.setContributorId(artifact.getContributor().getId());
            String fullName = (artifact.getContributor().getLastName() != null ? artifact.getContributor().getLastName() : "") + " "
                    + (artifact.getContributor().getFirstName() != null ? artifact.getContributor().getFirstName() : "");
            response.setContributorName(!fullName.trim().isEmpty() ? fullName.trim() : artifact.getContributor().getUsername());
        } else {
            response.setContributorName(artifact.getContributorName());
        }

        response.setArtifactEra(artifact.getArtifactEra());
        response.setPublicDate(artifact.getPublicDate());
        response.setLocation(artifact.getLocation());
        response.setApprovalStatus(artifact.getApprovalStatus());
        response.setAdminNote(artifact.getAdminNote());
        response.setCreatedAt(artifact.getCreatedAt());
        response.setUpdatedAt(artifact.getUpdatedAt());
        response.setApprovedAt(artifact.getApprovedAt());

        return response;
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getShortDescription() {
        return shortDescription;
    }

    public void setShortDescription(String shortDescription) {
        this.shortDescription = shortDescription;
    }

    public String getDescription() {
        return description;
    }

    public void setDescription(String description) {
        this.description = description;
    }

    public String getCategories() {
        return categories;
    }

    public void setCategories(String categories) {
        this.categories = categories;
    }

    public String getMainImageUrl() {
        return mainImageUrl;
    }

    public void setMainImageUrl(String mainImageUrl) {
        this.mainImageUrl = mainImageUrl;
    }

    public String getSupportingImages() {
        return supportingImages;
    }

    public void setSupportingImages(String supportingImages) {
        this.supportingImages = supportingImages;
    }

    public String getAuthor() {
        return author;
    }

    public void setAuthor(String author) {
        this.author = author;
    }

    public String getContributorName() {
        return contributorName;
    }

    public void setContributorName(String contributorName) {
        this.contributorName = contributorName;
    }

    public Long getContributorId() {
        return contributorId;
    }

    public void setContributorId(Long contributorId) {
        this.contributorId = contributorId;
    }

    public String getArtifactEra() {
        return artifactEra;
    }

    public void setArtifactEra(String artifactEra) {
        this.artifactEra = artifactEra;
    }

    public String getPublicDate() {
        return publicDate;
    }

    public void setPublicDate(String publicDate) {
        this.publicDate = publicDate;
    }

    public String getLocation() {
        return location;
    }

    public void setLocation(String location) {
        this.location = location;
    }

    public String getApprovalStatus() {
        return approvalStatus;
    }

    public void setApprovalStatus(String approvalStatus) {
        this.approvalStatus = approvalStatus;
    }

    public String getAdminNote() {
        return adminNote;
    }

    public void setAdminNote(String adminNote) {
        this.adminNote = adminNote;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(OffsetDateTime createdAt) {
        this.createdAt = createdAt;
    }

    public OffsetDateTime getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(OffsetDateTime updatedAt) {
        this.updatedAt = updatedAt;
    }

    public OffsetDateTime getApprovedAt() {
        return approvedAt;
    }

    public void setApprovedAt(OffsetDateTime approvedAt) {
        this.approvedAt = approvedAt;
    }
}
