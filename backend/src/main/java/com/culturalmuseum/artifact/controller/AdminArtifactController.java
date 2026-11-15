package com.culturalmuseum.artifact.controller;

import com.culturalmuseum.artifact.dto.request.ArtifactCreationRequest;
import com.culturalmuseum.artifact.dto.request.ArtifactRejectRequest;
import com.culturalmuseum.artifact.dto.request.ArtifactUpdateRequest;
import com.culturalmuseum.artifact.dto.response.ArtifactResponse;
import com.culturalmuseum.artifact.service.ArtifactService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/admin/artifact")
@SecurityRequirement(name = "BearerAuth")
@Tag(name = "Artifacts (Admin)", description = "Private endpoints for Admin to review, approve, and manage artifacts")
public class AdminArtifactController {

    private final ArtifactService artifactService;

    public AdminArtifactController(ArtifactService artifactService) {
        this.artifactService = artifactService;
    }

    // 1. ADMIN XEM DANH SÁCH HIỆN VẬT CHỜ DUYỆT (PENDING)
    @GetMapping("/pending")
    @Operation(summary = "View pending artifacts", description = "Retrieves a list of all active artifacts awaiting admin approval (PENDING)")
    @ApiResponses(value = {
            @ApiResponse(responseCode = "200", description = "List retrieved successfully"),
            @ApiResponse(responseCode = "401", description = "Unauthorized - Missing or invalid JWT token")
    })
    public List<ArtifactResponse> getPendingArtifacts() {
        return artifactService.getPendingArtifacts();
    }

    // 2. ADMIN DUYỆT HIỆN VẬT (APPROVED)
    @PutMapping("/{id}/approve")
    @Operation(summary = "Approve artifact", description = "Approves a pending artifact, making it public (APPROVED)")
    @ApiResponses(value = {
            @ApiResponse(responseCode = "200", description = "Artifact approved successfully"),
            @ApiResponse(responseCode = "404", description = "Artifact not found")
    })
    public ArtifactResponse approveArtifact(
            @Parameter(description = "ID of the artifact to be approved", example = "1")
            @PathVariable Long id) {
        return artifactService.approveArtifact(id);
    }

    // 3. ADMIN TỪ CHỐI HIỆN VẬT (REJECTED)
    @PutMapping("/{id}/reject")
    @Operation(summary = "Reject artifact", description = "Rejects a pending artifact and saves the reason for rejection (adminNote)")
    @ApiResponses(value = {
            @ApiResponse(responseCode = "200", description = "Artifact rejected successfully"),
            @ApiResponse(responseCode = "404", description = "Artifact not found")
    })
    public ArtifactResponse rejectArtifact(
            @Parameter(description = "ID of the artifact to be rejected", example = "1")
            @PathVariable Long id,
            @RequestBody ArtifactRejectRequest request) {
        return artifactService.rejectArtifact(id, request.getAdminNote());
    }

    // ===============================================
    // CÁC HÀM QUẢN TRỊ TOÀN QUYỀN (FULL CRUD CHO ADMIN)
    // ===============================================

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @Operation(summary = "Admin create artifact directly", description = "Directly creates an artifact bypassing the pending workflow. Default status is APPROVED.")
    public ArtifactResponse createArtifactByAdmin(@RequestBody ArtifactCreationRequest request) {
        return artifactService.createArtifactByAdmin(request);
    }

    @PutMapping("/{id}")
    @Operation(summary = "Admin update any artifact details", description = "Updates details of an artifact, including adminNote or approvalStatus")
    public ArtifactResponse updateArtifact(
            @Parameter(description = "ID of the artifact", example = "1") @PathVariable Long id,
            @RequestBody ArtifactUpdateRequest request) {
        return artifactService.updateArtifact(id, request);
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    @Operation(summary = "Admin soft delete artifact", description = "Deactivates an artifact (status = 0)")
    public void deleteArtifact(@Parameter(description = "ID of the artifact", example = "1") @PathVariable Long id) {
        artifactService.deleteArtifact(id);
    }
}
