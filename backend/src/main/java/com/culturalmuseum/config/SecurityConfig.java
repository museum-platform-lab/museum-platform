package com.culturalmuseum.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

@Configuration
@EnableWebSecurity
public class SecurityConfig {

    private final JwtAuthenticationFilter jwtAuthenticationFilter;

    public SecurityConfig(JwtAuthenticationFilter jwtAuthenticationFilter) {
        this.jwtAuthenticationFilter = jwtAuthenticationFilter;
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
                // 1. Tắt CSRF vì hệ thống dùng Stateless REST API với JWT Token
                .csrf(AbstractHttpConfigurer::disable)

                // 2. Không sử dụng HTTP Session (Stateless)
                .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))

                // 3. Cấu hình phân quyền chi tiết (Public vs Private)
                .authorizeHttpRequests(auth -> auth
                        // 🟢 PUBLIC 1: Swagger & OpenAPI Documentation (Tự do truy cập)
                        .requestMatchers(
                                "/swagger-ui/**",
                                "/swagger-ui.html",
                                "/v3/api-docs/**",
                                "/swagger-resources/**",
                                "/webjars/**"
                        ).permitAll()

                        // 🟢 PUBLIC 2: Đăng ký & Đăng nhập (/auth, /auth/login)
                        .requestMatchers(HttpMethod.POST, "/auth", "/auth/login").permitAll()

                        // 🟢 PUBLIC 3: Xem danh sách và chi tiết hiện vật (GET /artifact/**)
                        .requestMatchers(HttpMethod.GET, "/artifact/**").permitAll()

                        // 🔴 PRIVATE 1: Bắt buộc Login khi đóng góp hiện vật
                        .requestMatchers(HttpMethod.POST, "/artifact/contribute").authenticated()

                        // 🔴 PRIVATE 2: Bắt buộc Login đối với các API quản trị Admin
                        .requestMatchers("/admin/**").authenticated()

                        // Mọi API còn lại (như GET/PUT/DELETE /auth/**) cũng yêu cầu xác thực hoặc cấu hình thêm
                        .anyRequest().permitAll()
                )

                // 4. Đặt JwtAuthenticationFilter trước UsernamePasswordAuthenticationFilter
                .addFilterBefore(jwtAuthenticationFilter, UsernamePasswordAuthenticationFilter.class);

        return http.build();
    }
}
