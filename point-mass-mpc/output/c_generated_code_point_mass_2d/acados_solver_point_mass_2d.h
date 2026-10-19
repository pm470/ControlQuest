/*
 * Copyright (c) The acados authors.
 *
 * This file is part of acados.
 *
 * The 2-Clause BSD License
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *
 * 1. Redistributions of source code must retain the above copyright notice,
 * this list of conditions and the following disclaimer.
 *
 * 2. Redistributions in binary form must reproduce the above copyright notice,
 * this list of conditions and the following disclaimer in the documentation
 * and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
 * LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.;
 */

#ifndef ACADOS_SOLVER_point_mass_2d_H_
#define ACADOS_SOLVER_point_mass_2d_H_

#include "acados/utils/types.h"

#include "acados_c/ocp_nlp_interface.h"
#include "acados_c/external_function_interface.h"

#define POINT_MASS_2D_NX     4
#define POINT_MASS_2D_NZ     0
#define POINT_MASS_2D_NU     2
#define POINT_MASS_2D_NP     0
#define POINT_MASS_2D_NP_GLOBAL     0
#define POINT_MASS_2D_NBX    4
#define POINT_MASS_2D_NBX0   4
#define POINT_MASS_2D_NBU    2
#define POINT_MASS_2D_NSBX   0
#define POINT_MASS_2D_NSBU   0
#define POINT_MASS_2D_NSH    0
#define POINT_MASS_2D_NSH0   0
#define POINT_MASS_2D_NSG    0
#define POINT_MASS_2D_NSPHI  0
#define POINT_MASS_2D_NSHN   0
#define POINT_MASS_2D_NSGN   0
#define POINT_MASS_2D_NSPHIN 0
#define POINT_MASS_2D_NSPHI0 0
#define POINT_MASS_2D_NSBXN  0
#define POINT_MASS_2D_NS     0
#define POINT_MASS_2D_NS0    0
#define POINT_MASS_2D_NSN    0
#define POINT_MASS_2D_NG     0
#define POINT_MASS_2D_NBXN   4
#define POINT_MASS_2D_NGN    0
#define POINT_MASS_2D_NY0    6
#define POINT_MASS_2D_NY     6
#define POINT_MASS_2D_NYN    4
#define POINT_MASS_2D_N      30
#define POINT_MASS_2D_NH     0
#define POINT_MASS_2D_NHN    0
#define POINT_MASS_2D_NH0    0
#define POINT_MASS_2D_NPHI0  0
#define POINT_MASS_2D_NPHI   0
#define POINT_MASS_2D_NPHIN  0
#define POINT_MASS_2D_NR     0

#ifdef __cplusplus
extern "C" {
#endif


// ** capsule for solver data **
typedef struct point_mass_2d_solver_capsule
{
    // acados objects
    ocp_nlp_in *nlp_in;
    ocp_nlp_out *nlp_out;
    ocp_nlp_out *sens_out;
    ocp_nlp_solver *nlp_solver;
    void *nlp_opts;
    ocp_nlp_plan_t *nlp_solver_plan;
    ocp_nlp_config *nlp_config;
    ocp_nlp_dims *nlp_dims;

    // number of expected runtime parameters
    unsigned int nlp_np;

    /* external functions */

    // dynamics

    external_function_external_param_casadi *discr_dyn_phi_fun;
    external_function_external_param_casadi *discr_dyn_phi_fun_jac_ut_xt;




    // cost






    // constraints







} point_mass_2d_solver_capsule;

ACADOS_SYMBOL_EXPORT point_mass_2d_solver_capsule * point_mass_2d_acados_create_capsule(void);
ACADOS_SYMBOL_EXPORT int point_mass_2d_acados_free_capsule(point_mass_2d_solver_capsule *capsule);

ACADOS_SYMBOL_EXPORT int point_mass_2d_acados_create(point_mass_2d_solver_capsule * capsule);

ACADOS_SYMBOL_EXPORT int point_mass_2d_acados_reset(point_mass_2d_solver_capsule* capsule, int reset_qp_solver_mem);

/**
 * Generic version of point_mass_2d_acados_create which allows to use a different number of shooting intervals than
 * the number used for code generation. If new_time_steps=NULL and n_time_steps matches the number used for code
 * generation, the time-steps from code generation is used.
 */
ACADOS_SYMBOL_EXPORT int point_mass_2d_acados_create_with_discretization(point_mass_2d_solver_capsule * capsule, int n_time_steps, double* new_time_steps);
/**
 * Update the time step vector. Number N must be identical to the currently set number of shooting nodes in the
 * nlp_solver_plan. Returns 0 if no error occurred and a otherwise a value other than 0.
 */
ACADOS_SYMBOL_EXPORT int point_mass_2d_acados_update_time_steps(point_mass_2d_solver_capsule * capsule, int N, double* new_time_steps);
/**
 * This function is used for updating an already initialized solver with a different number of qp_cond_N.
 */
ACADOS_SYMBOL_EXPORT int point_mass_2d_acados_update_qp_solver_cond_N(point_mass_2d_solver_capsule * capsule, int qp_solver_cond_N);
ACADOS_SYMBOL_EXPORT int point_mass_2d_acados_update_params(point_mass_2d_solver_capsule * capsule, int stage, double *value, int np);
ACADOS_SYMBOL_EXPORT int point_mass_2d_acados_update_params_sparse(point_mass_2d_solver_capsule * capsule, int stage, int *idx, double *p, int n_update);
ACADOS_SYMBOL_EXPORT int point_mass_2d_acados_set_p_global_and_precompute_dependencies(point_mass_2d_solver_capsule* capsule, double* data, int data_len);

ACADOS_SYMBOL_EXPORT int point_mass_2d_acados_solve(point_mass_2d_solver_capsule * capsule);
ACADOS_SYMBOL_EXPORT int point_mass_2d_acados_setup_qp_matrices_and_factorize(point_mass_2d_solver_capsule* capsule);



ACADOS_SYMBOL_EXPORT int point_mass_2d_acados_free(point_mass_2d_solver_capsule * capsule);
ACADOS_SYMBOL_EXPORT void point_mass_2d_acados_print_stats(point_mass_2d_solver_capsule * capsule);
ACADOS_SYMBOL_EXPORT int point_mass_2d_acados_custom_update(point_mass_2d_solver_capsule* capsule, double* data, int data_len);

ACADOS_SYMBOL_EXPORT ocp_nlp_in *point_mass_2d_acados_get_nlp_in(point_mass_2d_solver_capsule * capsule);
ACADOS_SYMBOL_EXPORT ocp_nlp_out *point_mass_2d_acados_get_nlp_out(point_mass_2d_solver_capsule * capsule);
ACADOS_SYMBOL_EXPORT ocp_nlp_out *point_mass_2d_acados_get_sens_out(point_mass_2d_solver_capsule * capsule);
ACADOS_SYMBOL_EXPORT ocp_nlp_solver *point_mass_2d_acados_get_nlp_solver(point_mass_2d_solver_capsule * capsule);
ACADOS_SYMBOL_EXPORT ocp_nlp_config *point_mass_2d_acados_get_nlp_config(point_mass_2d_solver_capsule * capsule);
ACADOS_SYMBOL_EXPORT void *point_mass_2d_acados_get_nlp_opts(point_mass_2d_solver_capsule * capsule);
ACADOS_SYMBOL_EXPORT ocp_nlp_dims *point_mass_2d_acados_get_nlp_dims(point_mass_2d_solver_capsule * capsule);
ACADOS_SYMBOL_EXPORT ocp_nlp_plan_t *point_mass_2d_acados_get_nlp_plan(point_mass_2d_solver_capsule * capsule);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif  // ACADOS_SOLVER_point_mass_2d_H_
