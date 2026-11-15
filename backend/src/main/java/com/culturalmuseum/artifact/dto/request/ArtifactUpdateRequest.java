package com.culturalmuseum.artifact.dto.request;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "Request payload for updating an existing artifact")
public class ArtifactUpdateRequest {

    @Schema(description = "Name of the artifact", example = "Dong Son Bronze Drum")
    private String name;

    @Schema(description = "Brief summary of the artifact", example = "Iconic bronze drum representing Dong Son culture")
    private String shortDescription;

    @Schema(description = "Detailed historical and cultural description")
    private String description;

    @Schema(description = "Category or genre tags", example = "Bronze Age, Archeological Relic")
    private String categories;

    @Schema(description = "Direct URL to the main display image")
    private String mainImageUrl;

    @Schema(description = "URLs of supporting images")
    private String supportingImages;

    @Schema(description = "Author, craftsman, or culture creator")
    private String author;

    @Schema(description = "Contributor display name")
    private String contributorName;

    @Schema(description = "Historical era or dynasty")
    private String artifactEra;

    @Schema(description = "Public release or discovery date/year")
    private String publicDate;

    @Schema(description = "Current gallery location")
    private String location;

    @Schema(description = "Approval status (PENDING, APPROVED, REJECTED)", example = "APPROVED")
    private String approvalStatus;

    @Schema(description = "Admin note or feedback")
    private String adminNote;

    public ArtifactUpdateRequest() {
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
}
