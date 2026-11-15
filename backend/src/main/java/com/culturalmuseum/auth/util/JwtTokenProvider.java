package com.culturalmuseum.auth.util;

import com.culturalmuseum.auth.entity.User;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;

@Component
public class JwtTokenProvider {

    // Khóa bí mật ký số (HMAC-SHA256 yêu cầu tối thiểu 256 bits / 32 ký tự)
    @org.springframework.beans.factory.annotation.Value("${museum.jwt.secret}")
    private String jwtSecret;

    // Thời gian sống của Token: 24 giờ (tính bằng mili-giây)
    private static final long JWT_EXPIRATION_MS = 24 * 60 * 60 * 1000L;

    private SecretKey getSigningKey() {
        return Keys.hmacShaKeyFor(jwtSecret.getBytes(StandardCharsets.UTF_8));
    }

    // 1. Tạo chuỗi JWT Token từ thông tin User
    public String generateToken(User user) {
        Date now = new Date();
        Date expiryDate = new Date(now.getTime() + JWT_EXPIRATION_MS);

        return Jwts.builder()
                .subject(user.getId().toString()) // Subject là User ID
                .claim("username", user.getUsername())
                .claim("role", user.getRole())
                .claim("email", user.getEmail())
                .issuedAt(now)
                .expiration(expiryDate)
                .signWith(getSigningKey())
                .compact();
    }

    // 2. Trích xuất User ID từ Token
    public Long getUserIdFromToken(String token) {
        Claims claims = getClaimsFromToken(token);
        return Long.parseLong(claims.getSubject());
    }

    // 3. Trích xuất Username từ Token
    public String getUsernameFromToken(String token) {
        Claims claims = getClaimsFromToken(token);
        return claims.get("username", String.class);
    }

    // 4. Kiểm tra Token có hợp lệ và còn hạn sử dụng không
    public boolean validateToken(String token) {
        try {
            getClaimsFromToken(token);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    private Claims getClaimsFromToken(String token) {
        return Jwts.parser()
                .verifyWith(getSigningKey())
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }
}
