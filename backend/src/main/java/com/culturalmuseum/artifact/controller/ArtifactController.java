package com.culturalmuseum.artifact.controller;

import com.culturalmuseum.artifact.dto.request.ArtifactCreationRequest;
import com.culturalmuseum.artifact.dto.response.ArtifactResponse;
import com.culturalmuseum.artifact.service.ArtifactService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/artifact")
@Tag(name = "Artifacts (Public)", description = "Public endpoints for exploring cultural artifacts and User contribution")
public class ArtifactController {

    private final ArtifactService artifactService;

    public ArtifactController(ArtifactService artifactService) {
        this.artifactService = artifactService;
    }

    // 1. GUEST: XEM TẤT CẢ HIỆN VẬT ĐÃ ĐƯỢC DUYỆT (PUBLIC)
    @GetMapping
    @Operation(summary = "View public artifacts", description = "Retrieves a list of all active and APPROVED museum artifacts")
    @ApiResponses(value = {
            @ApiResponse(responseCode = "200", description = "Artifacts retrieved successfully")
    })
    public List<ArtifactResponse> getPublicArtifacts() {
        return artifactService.getPublicArtifacts();
    }

    // 2. GUEST: XEM CHI TIẾT HIỆN VẬT (PUBLIC)
    @GetMapping("/{id}")
    @Operation(summary = "View artifact details", description = "Retrieves information of an existing APPROVED artifact by its ID")
    @ApiResponses(value = {
            @ApiResponse(responseCode = "200", description = "Artifact found"),
            @ApiResponse(responseCode = "404", description = "Artifact not found, deactivated, or not approved")
    })
    public ArtifactResponse getPublicArtifactById(
            @Parameter(description = "ID of the artifact to be viewed", example = "1")
            @PathVariable Long id) {
        return artifactService.getPublicArtifactById(id);
    }

    // 3. USER: GỬI HIỆN VẬT ĐÓNG GÓP TỚI KHO TẠM CHỜ DUYỆT (PRIVATE)
    @PostMapping("/contribute")
    @ResponseStatus(HttpStatus.CREATED)
    @SecurityRequirement(name = "BearerAuth")
    @Operation(summary = "Contribute a new artifact (Requires Login)", description = "Logged-in users can contribute an artifact. It will be placed in PENDING state awaiting Admin approval.")
    @ApiResponses(value = {
            @ApiResponse(responseCode = "201", description = "Artifact contributed successfully and is PENDING"),
            @ApiResponse(responseCode = "401", description = "Unauthorized - Missing or invalid JWT token"),
            @ApiResponse(responseCode = "400", description = "Invalid request payload")
    })
    public ArtifactResponse contributeArtifact(@RequestBody ArtifactCreationRequest request) {
        // Lấy ID người dùng hiện tại từ chuỗi JWT đã được lọc thành Authorization Principal
        Long contributorId = (Long) SecurityContextHolder.getContext().getAuthentication().getPrincipal();
        return artifactService.createContributedArtifact(request, contributorId);
    }
}
