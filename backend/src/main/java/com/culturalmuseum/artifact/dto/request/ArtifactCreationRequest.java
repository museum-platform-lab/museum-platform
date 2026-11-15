package com.culturalmuseum.artifact.dto.request;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "Request payload for creating a new artifact")
public class ArtifactCreationRequest {

    @Schema(description = "Name of the artifact", example = "Dong Son Bronze Drum", requiredMode = Schema.RequiredMode.REQUIRED)
    private String name;

    @Schema(description = "Brief summary of the artifact", example = "Iconic bronze drum representing the prehistoric Dong Son culture")
    private String shortDescription;

    @Schema(description = "Detailed historical and cultural description", example = "The Dong Son bronze drums were created by the Dong Son culture in ancient Vietnam...")
    private String description;

    @Schema(description = "Category or genre tags", example = "Bronze Age, Archeological Relic")
    private String categories;

    @Schema(description = "Direct URL to the main display image", example = "https://example.com/images/dong-son-drum.jpg")
    private String mainImageUrl;

    @Schema(description = "URLs of supporting images (comma-separated or list)", example = "https://example.com/img1.jpg,https://example.com/img2.jpg")
    private String supportingImages;

    @Schema(description = "Author, craftsman, or culture creator", example = "Lac Viet People")
    private String author;

    @Schema(description = "Name of the contributor / donor", example = "Nguyen Van An")
    private String contributorName;

    @Schema(description = "ID of the user account contributing (if logged in)", example = "1")
    private Long contributorId;

    @Schema(description = "Historical era or dynasty", example = "Dong Son Culture (c. 1000 BC - 1st century AD)")
    private String artifactEra;

    @Schema(description = "Public release or discovery date/year", example = "1924")
    private String publicDate;

    @Schema(description = "Current gallery or exhibition location", example = "Exhibition Hall 1 - National History Museum")
    private String location;

    public ArtifactCreationRequest() {
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
}
